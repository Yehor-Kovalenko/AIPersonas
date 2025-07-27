import logging


def transcribe_audio_file(model, file_path):
    logging.info(f"Transcribing file: {file_path}")
    try:
        result = model.transcribe(file_path)
        logging.debug(f"Raw transcription result: {result}")
        text = result.get("text", "").strip()
        language = result.get("language", "unknown")
        if not text:
            logging.warning("No speech detected in the audio.")
            return {
                "text": "(No speech detected)",
                "language": language
            }
        logging.info("Transcription complete.")
        return {
            "text": text,
            "language": language
        }

    except Exception as e:
        logging.error(f"Error during transcription: {e}")
        raise