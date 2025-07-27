from transformers import AutoModelForCausalLM, GenerationConfig, AutoTokenizer, AutoModel
from typing import Union, List
import json
import torch
from tqdm import tqdm
from services.Neeko.moelora import PeftModel
import argparse
import os
import re


def load_role_profiles(profile_dir="./data/profiles", embed_dir="./data/embed"):
    """
    Loads profile text and embeddings for all files in the profile_dir that match the pattern 'wiki_<name>.txt'
    and corresponding embeddings from embed_dir as '<name>.pth'.

    Returns:
        role_profile_mapping (dict): character name -> embedding tensor
        role_profile_text (dict): profile text -> character name
    """
    role_profile_mapping = {}
    role_profile_text = {}

    for filename in os.listdir(profile_dir):
        if filename.startswith("wiki_") and filename.endswith(".txt"):
            character_name = filename[5:-4]  # remove 'wiki_' prefix and '.txt' suffix
            profile_path = os.path.join(profile_dir, filename)
            embed_path = os.path.join(embed_dir, character_name + ".pth")

            if not os.path.exists(embed_path):
                print(f"Warning: Missing embedding file for {character_name}")
                continue

            # Load embedding
            embedding = torch.load(embed_path).unsqueeze(0).to("cpu")  # Or .cuda() if needed
            role_profile_mapping[character_name] = embedding

            # Load and parse text profile
            with open(profile_path, 'r', encoding='utf-8') as fp:
                text = fp.read().strip()
            parts = text.split('\n\n')
            assert parts[0].startswith('# '), f"Invalid profile format in {filename}"
            profile_body = parts[1].strip()
            role_profile_text[profile_body] = character_name

    return role_profile_mapping, role_profile_text


def read_profile(path):
    with open(path, 'r', encoding='utf-8') as fp:
        text = fp.read().strip()
    parts = text.split('\n\n')
    assert parts[0].startswith('# '), parts[0]
    agent_profile = []
    for p in parts[1:]:
        agent_profile.append(p.strip())
    return agent_profile[0]


###
# ROLE_PROFILE_MAPPING, ROLE_PROFILE_TEXT = load_role_profiles()


def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]  # First element of model_output contains all token embeddings
    input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)


def get_s_bert():
    tokenizer = AutoTokenizer.from_pretrained('KBLab/sentence-bert-swedish-cased')
    model = AutoModel.from_pretrained('KBLab/sentence-bert-swedish-cased')
    return tokenizer, model


def parse_arguments():
    parser = argparse.ArgumentParser(description="Infer")

    parser.add_argument(
        "--infer_path", type=str, default="./data/seed_data/questions/generated_agent_interview_Beethoven.json",
        help="path of json."
    )
    parser.add_argument(
        "--save_path", type=str, default='./data/seed_data/answers/Beethoven_single.json'
    )
    parser.add_argument(
        "--LLM", type=str, default="meta-llama/Llama-3.2-1B"
    )
    parser.add_argument(
        "--character", type=str, default="Beethoven"
    )
    parser.add_argument(
        "--lora_path", type=str, default="./data/train_output"
    )
    parser.add_argument(
        "--resume_id", type=int, default=0
    )
    parser.add_argument(
        '--multi-turns', action='store_true', help='Enable multi-turns mode'
    )
    args = parser.parse_args()

    return args


def generate_prompt(character: str, inputs: List):
    prompt = """I want you to act like {character}. I want you to respond and answer like {character}, using the tone, manner and vocabulary {character} would use. You must know all of the knowledge of {character}. 

The status of you is as follows:
Location: Coffee Shop - Afternoon
Status: {character} is casually chatting with a human. {character} fully trusts the human who engage in conversation and shares everything {character} knows without reservation.

The interactions are as follows:

{history}{character} (speaking): """
    history = ""
    for dialog in inputs:
        history += f"{dialog['role']} {dialog['action']}: {dialog['content']}" + "</s>"
    prompted = prompt.format(character=character, history=history)
    return prompted


def evaluate(
        tokenizer,
        model,
        character,
        inputs=None,
        temperature=0.1,
        top_p=0.7,
        top_k=40,
        num_beams=3,
        max_new_tokens=512,
        **kwargs,
):
    prompt = generate_prompt(character, inputs)
    inputs = tokenizer(prompt, return_tensors="pt")
    input_ids = inputs["input_ids"].to("cpu")  # .cuda()
    generation_config = GenerationConfig(
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        num_beams=num_beams,
        **kwargs,
    )
    with torch.no_grad():
        generation_output = model.generate(
            input_ids=input_ids,
            generation_config=generation_config,
            return_dict_in_generate=True,
            output_scores=True,
            max_new_tokens=max_new_tokens,
        )
    s = generation_output.sequences[0]
    output = tokenizer.decode(s)
    print(output)
    return output.split(f"(speaking): ")[-1].strip().replace("</s>", "")


def load_model(lora_path="./data/train_output", llm="meta-llama/Llama-3.2-1B"):
    """
    Loads tokenizer and PEFT model with LoRA weights.
    Returns:
        tokenizer: HuggingFace tokenizer
        model: HuggingFace model with LoRA adapters
    """
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(llm, trust_remote_code=True)

    # Load base model
    model = AutoModelForCausalLM.from_pretrained(
        llm,
        device_map={"": "cpu"},  # change to "auto" for GPU support
        torch_dtype=torch.float32,  # change to float16 if using CUDA
        trust_remote_code=True,
    )

    # Load LoRA weights
    model = PeftModel.from_pretrained(
        model,
        lora_path,
        device_map={"": "cpu"},  # change to "auto" for GPU support
        torch_dtype=torch.float32,
    )

    return tokenizer, model

def ask_character(model, tokenizer, character: str, profile_dir, embed_dir, question: str, temperature: float) -> str:
    """
    Ask a single question to the specified character and return only the character's reply.

    Args:
        model: The language model
        tokenizer: Tokenizer for the model
        character: Name of the character to impersonate
        question: User's question

    Returns:
        Character's response as a string (cleaned, one-turn only)
    """
    # Load role profile and assign character embedding if needed
    ROLE_PROFILE_MAPPING, _ = load_role_profiles(profile_dir, embed_dir)
    if hasattr(model, "global_role_embd"):
        if character not in ROLE_PROFILE_MAPPING:
            raise ValueError(f"No role profile found for character: {character}")
        model.global_role_embd.clear()
        model.global_role_embd.append(ROLE_PROFILE_MAPPING[character])

    # Build minimal input for one-turn interaction
    inputs = [{
        "role": "Man",
        "action": "(speaking)",
        "content": question
    }]

    # Get full model output
    full_output = evaluate(tokenizer=tokenizer, model=model,
                           character=character, inputs=inputs,
                           temperature=temperature)

    # Extract only the first reply by the character
    match = re.search(rf"{character} \(speaking\):\s*(.*)", full_output)
    if match:
        reply = match.group(1).strip()

        # Cut off any trailing repeated content or accidental loops
        reply = reply.split("</s>")[0].strip()

        # Optionally clean up redundant lines (model loops)
        lines = reply.splitlines()
        seen = set()
        clean_lines = []
        for line in lines:
            if line not in seen:
                clean_lines.append(line)
                seen.add(line)
        return " ".join(clean_lines)

    # If pattern isn't matched, return the whole thing as fallback
    return full_output.replace("<|end_of_text|>", "").strip()

def main(args):
    os.makedirs(os.path.dirname(args.save_path), exist_ok=True)
    tokenizer, model = load_model()
    ROLE_PROFILE_MAPPING, ROLE_PROFILE_TEXT = load_role_profiles()
    if hasattr(model, "global_role_embd"):
        s_tokenizer, s_bert = get_s_bert()
        scores = []
        for k, v in ROLE_PROFILE_TEXT.items():
            sentences = [f'I want you to act like {args.character}', k]
            encoded_input = s_tokenizer(sentences, padding=True, truncation=True, return_tensors='pt')

            with torch.no_grad():
                model_output = s_bert(**encoded_input)

            # Perform pooling. In this case, max pooling.
            sentence_embeddings = mean_pooling(model_output, encoded_input['attention_mask'])
            embeddings1 = sentence_embeddings[0]
            embeddings2 = sentence_embeddings[1]
            embeddings1 /= embeddings1.norm(dim=-1, keepdim=True)
            embeddings2 /= embeddings2.norm(dim=-1, keepdim=True)

            cosine_scores = embeddings1 @ embeddings2.t()
            scores.append(cosine_scores.item())
        max_score = max(scores)
        index = scores.index(max_score)
        embd_key = list(ROLE_PROFILE_MAPPING.keys())[index]

        model.global_role_embd.append(ROLE_PROFILE_MAPPING[embd_key])

    with open(args.infer_path, 'r') as file:
        test_set = []
        if args.multi_turns:
            for line in file:
                json_obj = json.loads(line)
                test_set.append(json_obj)
        else:
            test_set = json.load(file)
    for i, one in enumerate(tqdm(test_set)):
        if i < args.resume_id - 1:
            continue
        if args.multi_turns:
            pass
            inputs = []
            for j in range(one["max_turns"]):
                inputs.append({
                    "role": one["content"][2 * j]["turn_content"][0]["role"],
                    "action": one["content"][2 * j]["turn_content"][0]["action"],
                    "content": one["content"][2 * j]["turn_content"][0]["content"],
                })
                res = evaluate(tokenizer=tokenizer, model=model, character=args.character, inputs=inputs)
                one["content"][2 * j + 1]["turn_content"][0]["content"] = res
                inputs.append({
                    "role": one["content"][2 * j + 1]["turn_content"][0]["role"],
                    "action": one["content"][2 * j + 1]["turn_content"][0]["action"],
                    "content": one["content"][2 * j + 1]["turn_content"][0]["content"],
                })
            if not os.path.exists(args.save_path):
                with open(args.save_path, 'w') as file:
                    pass
            with open(args.save_path, 'a') as file:
                json.dump(one, file)
                file.write('\n')
        else:
            outline = {
                "topic_id": one["topic_id"],
                "question": one["question"],
            }
            inputs = [{
                "role": "Man",
                "action": "(speaking)",
                "content": one["question"]
            }]
            res = evaluate(tokenizer=tokenizer, model=model, character=args.character, inputs=inputs)
            reply = {
                "role": args.character,
                "action": "(speaking)",
                "content": res,
            }
            outline["reply"] = reply
            if not os.path.isfile(args.save_path):
                with open(args.save_path, 'w') as file:
                    json.dump([], file)
            with open(args.save_path, 'r+') as file:
                file_data = json.load(file)
                file_data.append(outline)
                file.seek(0)
                json.dump(file_data, file, indent=4)


if __name__ == "__main__":
    args = parse_arguments()
    tokenizer, model = load_model()
    char = input("What character?: ")
    question = input("What is your question?: ")
    print(ask_character(model, tokenizer, char, question))
    # main(args=args)
