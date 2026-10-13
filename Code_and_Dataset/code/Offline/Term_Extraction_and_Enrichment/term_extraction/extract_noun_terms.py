import spacy
from srctoolkit import CodeChunker
from srctoolkit.delimiter import Delimiter
from definitions import DATA_DIR

nlp = spacy.load(DATA_DIR + "/spacy_model/en_core_web_sm-3.7.1/en_core_web_sm/en_core_web_sm-3.7.1")

_processed_words_cache = []


def _get_cached_nouns(word):
    """Get nouns from cache for already processed word"""
    for w in _processed_words_cache:
        if word == w['word']:
            return w['nouns']
    return None


def _pos_tagging(delimitered_word):
    """Perform part-of-speech tagging"""
    doc = nlp(delimitered_word)
    return [{'text': token.text, 'pos_': token.pos_} for token in doc]


def _extract_nouns_and_verbs(pos_result):
    """Extract nouns and verbs from POS tagging results"""
    nouns = []
    verbs = []
    for p in pos_result:
        if p['pos_'] == "VERB":
            verbs.append(p['text'])
        if p['pos_'] == "NOUN" or p['pos_'] == "PROPN":
            nouns.append(p['text'])
    return nouns, verbs


def _chunk_noun_phrases(string, keywords, nouns):
    """Identify noun phrases based on verbs"""
    chunker = CodeChunker.get_inst()
    temp_result = chunker.chunk(string, *keywords)
    result = []
    for k in keywords:
        if k in temp_result:
            ns = temp_result[k]
            for n in ns:
                if n != k and n not in result:
                    for noun in nouns:
                        if noun in n:
                            result.append(n)
                            break
    return result


def _lemmatize_nouns(nouns):
    """Lemmatize nouns to singular form"""
    lemmatized = []
    for n in nouns:
        doc = nlp(n)
        lemmatized_n = " ".join([
            token.text if token.text.lower() == "data" else token.lemma_ 
            for token in doc
        ])
        lemmatized.append(lemmatized_n)
    return lemmatized


def _extract_nouns_from_word(word):
    """
    Extract nouns from a single word
    
    Args:
        word: Identifier string
    
    Returns:
        list: Extracted noun list
    """
    cached_nouns = _get_cached_nouns(word)
    if cached_nouns is not None:
        return cached_nouns
    
    delimitered_words = Delimiter.split_camel(word)
    
    pos_result = _pos_tagging(delimitered_words)
    nouns, verbs = _extract_nouns_and_verbs(pos_result)
    
    if not verbs:
        final_nouns = nouns
    else:
        chunk_result = _chunk_noun_phrases(delimitered_words, verbs, nouns)
        if chunk_result:
            processed_chunk_result = []
            for ch in chunk_result:
                if ch.startswith("is "):
                    processed_chunk_result.append(ch[3:])
                elif ch.startswith("are "):
                    processed_chunk_result.append(ch[4:])
                else:
                    processed_chunk_result.append(ch)
            final_nouns = processed_chunk_result
        else:
            final_nouns = nouns
    
    lemmatized_nouns = _lemmatize_nouns(final_nouns)
    
    _processed_words_cache.append({'word': word, 'nouns': lemmatized_nouns})
    
    return lemmatized_nouns


def extract_nouns(words_data):
    """ Extract nouns from words data """
    
    result = []
    
    for item in words_data:
        temp = {
            'file_path': item['file_path'],
            'function_name': item['function_name'],
            'function_body': item['function_body'],
            'words': item['words'],
            'nouns': []
        }
        
        all_nouns = []
        for word in temp['words']:
            nouns = _extract_nouns_from_word(word)
            for noun in nouns:
                if noun not in all_nouns:
                    all_nouns.append(noun)
        
        temp['nouns'] = all_nouns
        result.append(temp)
    
    return result
