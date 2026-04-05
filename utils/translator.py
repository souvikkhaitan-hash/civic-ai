from deep_translator import GoogleTranslator

def translate_to_english(text):
    if not text: return None
    try:
        # Auto-detect source language and target English
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        
        # If the original text is already English, the translation will be identical (case-insensitive)
        if str(text).strip().lower() == str(translated).strip().lower():
            print(f"[TRANSLATOR] Input is already English. No translation stored.")
            return None
            
        print(f"[TRANSLATOR] Original: '{text[:30]}...' -> Translated: '{translated[:30]}...'")
        return translated
    except Exception as e:
        # No error logging, just return None if translation fails or input is English
        return None
