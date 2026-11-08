"""Voice NLU (file 05) against the test set in file 09."""
from __future__ import annotations

import pytest
import yaml

import settings
from nlu.evaluate import CASES, evaluate
from nlu.menu import load_menu
from nlu.normalize import normalize
from nlu.lexicon import load as load_lexicon
from nlu.parser import Parser
from nlu.phonetic import key
from nlu.transliterate import to_roman


@pytest.fixture(scope="module")
def parser(seeded_db):
    return Parser(load_menu(seeded_db))


def test_utterance_set_meets_targets(seeded_db):
    cases = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    assert len(cases) >= 60
    res = evaluate(seeded_db)
    assert res.item_accuracy >= 0.95, res.failures
    assert res.intent_accuracy >= 0.95, res.failures
    assert res.en_cases >= 60 and res.english_accuracy >= 0.90, res.failures
    assert res.p95_ms < 300


def test_intent_model_held_out(tmp_path):
    from nlu.train_intent import train
    out = train(save_to=tmp_path / "intent.joblib", verbose=False)
    assert out["held_out_accuracy"] >= 0.95


@pytest.mark.parametrize("a,b", [("makhani", "makhni"), ("makhani", "makhaani"), ("butter", "batar"),
                                 ("paneer", "panir"), ("chicken", "chikan"), ("kadai", "kadhai"),
                                 ("biryani", "biriyani")])
def test_phonetic_keys_collapse_spellings(a, b):
    assert key(a) == key(b)


def test_transliteration():
    assert to_roman("पनीर बटर मसाला") == "paneer batar masaala"
    assert normalize("पनीर बटर मसाला", load_lexicon()).text == "paneer batar masala"  # spelling variants
    assert to_roman("दाल मखनी") == "daal makhni"
    assert to_roman("रोटी") == "roti"


def test_number_words_and_imperatives():
    lex = load_lexicon()
    assert normalize("do naan", lex).text == "2 naan"
    assert normalize("nahi wo hata do", lex).text == "nahi wo hata do"
    assert normalize("ek dozen roti", lex).text == "12 roti"
    assert normalize("dedh plate", lex).text == "1.5 plate"
    assert normalize("um haan bhaiya ek dal", lex).clean == "1 dal"


def test_clarification_offers_two_or_three(parser):
    for text in ["paneer masala", "naan", "butter", "ek paneer"]:
        p = parser.parse(text)
        clar = [m for m in p.mentions if m.status == "clarify"]
        assert len(clar) == 1 and 2 <= len(clar[0].candidates) <= 3, text


def test_unrelated_words_are_not_dishes(parser):
    for text in ["thats all", "mera naam priya hai", "yes please", "naheen rahne do", "hold on one second"]:
        assert not parser.parse(text).mentions, text


def test_language_detection(parser):
    assert parser.parse("one butter chicken please").language == "en"
    assert parser.parse("mujhe ek dal makhani chahiye").language == "hinglish"
    assert parser.parse("एक दाल मखनी").language == "hi"


def test_language_pack_adds_words(seeded_db):
    p = Parser(load_menu(seeded_db), packs=("mr",))
    out = p.parse("don bhaat")  # Marathi: two plain rice
    assert out.mentions and out.mentions[0].candidates[0].name == "Steamed Rice" and out.mentions[0].qty == 2
