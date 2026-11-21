# Chinese query glossary

The glossary in `cedict-glosses.idx` is adapted from CC-CEDICT, the community-maintained Chinese–English dictionary published by MDBG. The original CEDICT project was started by Paul Andrew Denisowski, copyright 1997–1998.

The upstream dictionary and this adapted data file are licensed under [Creative Commons Attribution–ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/). Readers can obtain the source or submit corrections through the [official project and download page](https://www.mdbg.net/chinese/dictionary?page=cc-cedict).

The bundled adaptation extracts concise English senses, prioritizes explicitly technical definitions when supplied, and indexes simplified and traditional multisyllable headword forms for offline lookup. Pronunciations, explanatory examples and long definitions are omitted. The transformation is independent of all search evaluation questions and candidate papers.

Bundled source archive SHA-256 `3ced10407463910ab7c931727e9f4ab51ccf0c2570c30ddae9aa8cd7a4efad1c`. The compiler and its filtering rules are in [evaluation/build_zh_glossary.py](../../evaluation/build_zh_glossary.py). From the repository root, run `python evaluation/build_zh_glossary.py cedict_1_0_ts_utf-8_mdbg.txt.gz` on the official gzip input.

## Subject terminology

The separate `technical-names.tsv` contains normalized Chinese and English headings only. The build aligns source headings, removes acronym annotations and retains short searchable terms. It omits definitions, examples and branding.

- Portions of this glossary are adapted from Google's [Machine Learning Glossary](https://developers.google.com/machine-learning/glossary?hl=en) and [Simplified Chinese edition](https://developers.google.com/machine-learning/glossary?hl=zh-cn), shared under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The Python headwords are adapted from the Python Software Foundation and contributors' [Python glossary, Chinese edition](https://docs.python.org/zh-cn/3/glossary.html). Copyright © 2001 Python Software Foundation. All Rights Reserved. The [PSF License Version 2](PSF-LICENSE.txt) is included.

To reproduce the heading extraction, supply `--terminology-dir DIRECTORY` to the compiler with these saved source pages. The SHA-256 digests for the bundled input snapshots are below.

| Filename | SHA-256 |
| --- | --- |
| google-ml-en.html | 4687f94f024d4b34744cc73c5d708ecefb692f6304e576373ed52a121cc28285 |
| google-ml-zh.html | 32d62829907f6b0a071e6576ffbfb7ea61ea4f2fdf7c272f8b6caaa757c1c474 |
| python-zh.html | 6fa1b967717a1fb15271c85574abeecd99e5501a2b43e2fb9779a6c895086b13 |
