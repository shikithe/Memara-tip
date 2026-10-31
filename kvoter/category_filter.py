"""Exclude youth, women's and reserve teams from senior football matching."""
import re
import unicodedata

YOUTH = re.compile(r"(?<![a-z0-9])u[ -]?(?:1[5-9]|2[0-3])(?=$|[^a-z0-9])")
WOMEN = re.compile(r"(?<![a-z0-9])(?:women|woman|womens|ladies|frauen|feminines|feminine|femenino|femenina|zene|zenski|female)(?=$|[^a-z0-9])")
RESERVE = re.compile(r"(?<![a-z0-9])(?:reserves?|ii|iii|b[ -]?team|second[ -]?team)(?=$|[^a-z0-9])")
SUFFIX_B = re.compile(r"(?<![a-z0-9])[bc]$")

def category(name):
    text = unicodedata.normalize("NFKD", str(name or "")).casefold()
    text = "".join(char for char in text if not unicodedata.combining(char)).strip()
    if YOUTH.search(text):
        return "youth"
    if WOMEN.search(text):
        return "women"
    if RESERVE.search(text) or SUFFIX_B.search(text):
        return "reserve"
    return None

def excluded(home, away):
    return category(home) or category(away)
