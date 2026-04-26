# sparkit-science

Python SDK for the [SPARKIT scientific research API](https://sparkit.science).

## Install

    pip install sparkit-science

## Quick start

```python
from sparkit_science import SparkitClient

client = SparkitClient(api_key="sk_sparkit_YOUR_API_KEY")

response = client.research(
    "What is the role of BRCA1 in homologous recombination?"
)
print(response.answer_text)
```

See [sparkit.science/docs](https://sparkit.science/docs) for the full API reference.

## License

MIT
