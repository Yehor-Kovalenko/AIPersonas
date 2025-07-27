import json

from infer import load_model, ask_character


neeko_model = None
neeko_tokenizer = None

try:
    neeko_tokenizer, neeko_model = load_model(lora_path="data/train_output")
except Exception as e:
    raise e

with open('Neeko_test_prompts.json', 'r') as file:
    data = json.load(file)

import json

from infer import load_model, ask_character

neeko_model = None
neeko_tokenizer = None

try:
    neeko_tokenizer, neeko_model = load_model(lora_path="data/train_output")
except Exception as e:
    raise e

with open('Neeko_test_prompts.json', 'r') as file:
    data = json.load(file)

# Open an output text file for writing
with open('Neeko_test_results.txt', 'w', encoding='utf-8') as output_file:
    for category, characters in data.get('tests', {}).items():
        output_file.write(f"\nCategory: {category}\n")

        for character, questions in characters.items():
            if questions:
                output_file.write(f"\nPerforming tests for {character}:\n")
                for i in range(2):
                    question = questions[i]
                    output_file.write(f"  Test {i + 1}. Question: '{question}'\n")
                    generated_text = ask_character(
                        model=neeko_model,
                        tokenizer=neeko_tokenizer,
                        character=character,
                        profile_dir="data/seed_data/profiles",
                        embed_dir="data/embed",
                        question=question
                    )
                    output_file.write(f"  Test {i + 1}. Answer: '{generated_text}'\n")
            output_file.write('------------------------------------------------------------------------------\n')
        output_file.write('###################################################################################\n')



