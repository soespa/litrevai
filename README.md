# LitRevAI

[![PyPI - Version](https://img.shields.io/pypi/v/litrevai.svg)](https://pypi.org/project/litrevai)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/litrevai.svg)](https://pypi.org/project/litrevai)

-----


**Table of Contents**

- [Description](#description)
- [Installation](#installation)
- [License](#license)

## Description

LitRevAI is Python package that allows to perform systematic literature reviews using NLP methods.

## Installation

```console
pip install litrevai
```

## Basic Usage

```python

from litrevai import LiteratureReview

lr = LiteratureReview()

lr.import_zotero(filter_libraries=['Personal'])

project = lr.create_project(name='New Project')


```

## License

`litrevai` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
