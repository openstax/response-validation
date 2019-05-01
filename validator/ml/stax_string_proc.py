# -*- coding: utf-8 -*-
"""
Created on Thu Jan 14 21:11:03 2016

@author: drew
"""
import re
import pandas as pd
from nltk.corpus import stopwords
from nltk.corpus import words
from nltk.stem.snowball import SnowballStemmer
import collections


class StaxStringProc(object):
    def __init__(
        self,
        corpora_list=[
            "./openform/ml/corpora/all_plaintext.txt",
            "./openform/ml/corpora/big.txt",
        ],
        # corpora_list=['/Users/drew/Research/text_validation/corpora/all_plaintext.txt',
        #               '/Users/drew/Research/text_validation/corpora/big.txt'],
        parse_args=(True, False, True, True),
    ):

        # Set the parsing arguments
        (self.remove_stopwords,
         self.tag_numeric,
         self.correct_spelling,
         self.kill_nonwords,
         ) = parse_args

        # Alphabet
        self.alphabet = "abcdefghijklmnopqrstuvwxyz"

        # List of common garbage words
        # fmt: off
        self.common_garbage_words = set(['lo', 'ur', 'mn', 'nonsense_word', 'n/a', 'na', 'idk', 'lol', 'asdf', 'jk', 'zz', 'zzz', 'k', 'j', 'hi', 'n', 'id', 'blah', 'huh', 'wut', 'lmao', 'wat', 'hm', 'hmm', 'fml', 'shit', 'fuck'])  # noqa
        # fmt: on

        # Punctuation
        self.punctuation = set("!@#$%^.,")

        # Reserved tags
        self.reserved_tags = [
            "numeric_type_hex",
            "numeric_type_binary",
            "numeric_type_octal",
            "numeric_type_float",
            "numeric_type_int",
            "numeric_type_complex",
            "numeric_type_roman",
            "math_type",
            "common_garbage",
        ]

        # Set up the stemmer
        self.st = SnowballStemmer("english")

        # Update the set of nltk words with the additional corpora
        # TODO make the words come from a file rather than nltk
        self.all_words = set(words.words())
        self.all_words.update(self.reserved_tags)
        self.max_word_length = 20

        # Set up the stopwords, remove 'a' due to math issues
        # TODO make stops come from file rather than nltk
        self.stops = set(stopwords.words("english"))

        # Train the spelling corrector using all corpora
        train_text = ""
        for cfile in corpora_list:
            # words_in_file = file(cfile).read() #Not compatible with Python 2.7
            f = open(cfile, "r")
            words_in_file = f.read()  # works across versions
            self.all_words.update(self.get_all_words(words_in_file))
            train_text = train_text + words_in_file

        self.NWORDS = self.train(self.get_all_words(train_text))

    def get_all_words(self, text):
        return re.findall("[a-z]+", text.lower())

    def train(self, features):
        model = collections.defaultdict(int)  # Was lambda: 1 for python2
        for f in features:
            model[f] += 1
        return model

    def spell_correct(self, word):
        if (self.is_numeric(word) in self.reserved_tags) or (len(word) <= 5):
            return word
        else:
            candidates = (
                self.known([word])
                or self.known(self.edits1(word))
                or self.known_edits2(word)
                or [word]
            )
            return max(candidates, key=self.NWORDS.get)

    def known(self, words):
        return set(w for w in words if w in self.NWORDS)

    def edits1(self, word):
        s = [(word[:i], word[i:]) for i in range(len(word) + 1)]
        deletes = [a + b[1:] for a, b in s if b]
        transposes = [a + b[1] + b[0] + b[2:] for a, b in s if len(b) > 1]
        replaces = [a + c + b[1:] for a, b in s for c in self.alphabet if b]
        inserts = [a + c + b for a, b in s for c in self.alphabet]
        return set(deletes + transposes + replaces + inserts)

    def known_edits2(self, word):
        return set(
            e2
            for e1 in self.edits1(word)
            for e2 in self.edits1(e1)
            if e2 in self.NWORDS
        )

    def strip_punctuation(self, s):
        s = "".join(ch for ch in s if ch not in self.punctuation)
        return s

    def process_string(
        self,
        answer,
        remove_stopwords=None,
        tag_numeric=None,
        correct_spelling=None,
        kill_nonwords=None,
    ):

        # Allows a local override of the parser settings
        if correct_spelling is None:
            correct_spelling = self.correct_spelling
        if remove_stopwords is None:
            remove_stopwords = self.remove_stopwords
        if tag_numeric is None:
            tag_numeric = self.tag_numeric
        if kill_nonwords is None:
            kill_nonwords = self.kill_nonwords

        # Get the response text and parse into words
        answer_text = answer
        if pd.isnull(answer_text):
            answer_text = ""
        answer_text = self.strip_punctuation(answer_text)
        wordlist = answer_text.lower().split()
        # wordlist = [unicode(w, errors='ignore') for w in wordlist] # Python 2 version
        wordlist = [str(w) for w in wordlist]  # Python 3 version
        wordlist = [w[0 : min(self.max_word_length, len(w))] for w in wordlist]

        if len(wordlist) == 0:
            return list(["no_text"])

        if correct_spelling:
            wordlist = [self.spell_correct(w) for w in wordlist]

        # Remove stopwords if applicable
        if remove_stopwords:
            wordlist = [w for w in wordlist if w not in self.stops]

        # Identify numeric values or math and tag appropriately
        if tag_numeric:
            wordlist = [self.is_numeric(w) for w in wordlist]

        if kill_nonwords:
            wordlist = [
                w
                if w in self.all_words
                or self.is_numeric(w) in self.reserved_tags
                or self.st.stem(w) in self.all_words
                or w in self.reserved_tags
                else "nonsense_word"
                for w in wordlist
            ]

        return wordlist

    @staticmethod
    def is_numeric(lit):
        "Return either the type of string if numeric else return string"

        if len(lit) == 0:
            return lit

        # Handle '0'
        if lit == "0":
            return "numeric_type_0"
        # Hex/Binary
        litneg = lit[1:] if (lit[0] == "-" and len(lit) > 1) else lit
        if litneg[0] == "0":
            if len(litneg) == 1:
                return "numeric_type_0"
            if litneg[1] in "xX":
                try:
                    int(lit, 16)
                    return "numeric_type_hex"
                except ValueError:
                    pass
            elif litneg[1] in "bB":
                try:
                    int(lit, 2)
                    return "numeric_type_binary"
                except ValueError:
                    pass
            else:
                try:
                    int(lit, 8)
                    return "numeric_type_octal"
                except ValueError:
                    pass

        # Int/Float/Complex/Roman
        try:
            int(lit)
            return "numeric_type_int"
        except ValueError:
            pass
        try:
            float(lit)
            return "numeric_type_float"
        except ValueError:
            pass
        try:
            complex(lit)
            return "numeric_type_complex"
        except ValueError:
            pass
        try:
            # Return either the type of string if math else return string
            # fmt: off
            a=b=c=d=e=f=g=h=i=j=k=l=m=n=o=p=q=r=s=t=u=v=w=x=y=z=1  # noqa
            A=B=C=D=E=F=G=H=I=J=K=L=M=N=O=P=Q=R=S=T=U=V=W=X=Y=Z=1  # noqa
            # fmt: on
            pi = 3.14  # noqa
            temp_lit = lit

            # These three replaces are just to fake out Python . . .
            temp_lit.replace("^", "**")
            temp_lit.replace("=", "==")
            temp_lit.replace("_", "")

            # Find all number-letter-number combos and replace with a single var
            temp_lit = re.sub(r"\d*[a-zA-z]\d*", "x", temp_lit)

            eval(temp_lit)
            return "math_type"
        except:  # Any parsing error at all means it's not math  # noqa
            pass
        try:

            class RomanError(Exception):
                pass

            class OutOfRangeError(RomanError):
                pass

            class NotIntegerError(RomanError):
                pass

            class InvalidRomanNumeralError(RomanError):
                pass

            # Define digit mapping
            # fmt: off
            romanNumeralMap = (
                ("M",  1000),  # noqa
                ("CM",  900),  # noqa
                ("D",   500),  # noqa
                ("CD",  400),  # noqa
                ("C",   100),  # noqa
                ("XC",   90),  # noqa
                ("L",    50),  # noqa
                ("XL",   40),  # noqa
                ("X",    10),  # noqa
                ("IX",    9),  # noqa
                ("V",     5),  # noqa
                ("IV",    4),  # noqa
                ("I",     1),  # noqa
            )
            # fmt: on
            # Define pattern to detect valid Roman numerals
            romanNumeralPattern = re.compile(
                """
            ^                   # beginning of string
            M{0,4}              # thousands - 0 to 4 M's
            (CM|CD|D?C{0,3})    # hundreds - 900 (CM), 400 (CD), 0-300 (0 to 3 C's),
                                #            or 500-800 (D, followed by 0 to 3 C's)
            (XC|XL|L?X{0,3})    # tens - 90 (XC), 40 (XL), 0-30 (0 to 3 X's),
                                #        or 50-80 (L, followed by 0 to 3 X's)
            (IX|IV|V?I{0,3})    # ones - 9 (IX), 4 (IV), 0-3 (0 to 3 I's),
                                #        or 5-8 (V, followed by 0 to 3 I's)
            $                   # end of string
            """,
                re.VERBOSE,
            )

            lit_upper = lit.upper()
            if not lit_upper:
                raise (InvalidRomanNumeralError, "Input can not be blank")
            if not romanNumeralPattern.search(lit_upper):
                raise (
                    InvalidRomanNumeralError,
                    "Invalid Roman numeral: %s" % lit_upper,
                )

            result = 0
            index = 0
            for numeral, integer in romanNumeralMap:
                while lit_upper[index : index + len(numeral)] == numeral:
                    result += integer
                    index += len(numeral)
            return "numeric_type_roman"
        except:  # Nothing worked, return it # noqa
            return lit