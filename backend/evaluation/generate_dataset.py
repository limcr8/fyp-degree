"""
Generates a labeled crypto/financial test dataset for RoBERTa evaluation.
This script is standalone and does NOT touch the deployed model.

Design principle: Fake news is written in a professional, plausible style
(similar vocabulary to real news) so that models must rely on factual
content, not surface-level features like ALL CAPS or exclamation marks.
"""
import csv
import random
import os

random.seed(42)

# ---------------------------------------------------------------------------
# REAL TEMPLATES — factual, well-sourced financial reporting style
# ---------------------------------------------------------------------------
REAL_TEMPLATES = [
    # Crypto — market movements
    ("Bitcoin {action} {pct}% to ${price} on {date}, driven by {reason}. Trading volume reached ${vol}B across major exchanges.", "real", "crypto"),
    ("Ethereum {action} past ${eth_price} following the successful {event} upgrade on the mainnet. Developers confirmed all validators completed the transition smoothly.", "real", "crypto"),
    ("{company} announced a ${amount}M investment in blockchain infrastructure, partnering with {partner} to develop scalable solutions for enterprise clients.", "real", "crypto"),
    ("The SEC approved {company}'s application for a {fund_type}, marking a significant milestone for institutional crypto adoption in the United States.", "real", "crypto"),
    ("{exchange} officially listed {coin} for spot trading, with the pair opening at ${coin_price} against USDT.", "real", "crypto"),

    # Finance — monetary policy & earnings
    ("The Federal Reserve raised the federal funds rate by {basis} basis points to a target range of {rate_low}-{rate_high}%, citing persistent inflation pressures.", "real", "finance"),
    ("{company} reported Q{quarter} revenue of ${rev}B, representing a {yoy_change}% increase year-over-year and exceeding analyst expectations of ${rev_est}B.", "real", "finance"),
    ("Bank Negara Malaysia decided to maintain the Overnight Policy Rate at {opr}% during its monetary policy meeting, aligning with market consensus.", "real", "finance"),
    ("The IMF revised its global growth forecast to {growth}% for {year}, citing recovery in emerging markets and stabilizing commodity prices.", "real", "finance"),
    ("{company} completed its Series {series} funding round, raising ${amount}M at a valuation of ${valuation}B. The round was led by {investor}.", "real", "finance"),

    # Crypto — regulatory & institutional
    ("The European Union's Markets in Crypto-Assets regulation entered into force, establishing a comprehensive framework for crypto-asset issuers and service providers.", "real", "crypto"),
    ("{company} disclosed a {btc_amount} BTC position in its latest treasury report, representing approximately {pct}% of total reserves.", "real", "crypto"),
    ("The {country} central bank announced it would begin testing a {cbdc_type} in partnership with commercial banks, with trials expected to commence in {trial_month}.", "real", "crypto"),

    # Finance — market events
    ("Gold prices {action} to ${gold_price} per ounce as investors sought safe-haven assets amid geopolitical tensions in {region}.", "real", "finance"),
    ("Crude oil futures {action} {pct}% to ${oil_price} per barrel after OPEC+ announced a production {prod_action} of {barrels}M barrels per day.", "real", "finance"),
]

# ---------------------------------------------------------------------------
# FAKE TEMPLATES — plausible misinformation written in professional news style
# (no ALL CAPS, no exclamation marks — designed to be genuinely deceptive)
# ---------------------------------------------------------------------------
FAKE_TEMPLATES = [
    # Crypto — fabricated adoption / partnerships
    ("{company} has reportedly integrated {coin} as a primary reserve asset, according to sources familiar with the matter. The move could position the firm as the first major institution to adopt a crypto-first treasury strategy.", "fake", "crypto"),
    ("Internal documents suggest that {country}'s government is preparing to adopt {coin} as legal tender, following {precedent_country}'s precedent. A formal announcement is expected within weeks.", "fake", "crypto"),
    ("{company} is finalizing an agreement to acquire {target_company} for ${amount}B in a deal that would merge traditional finance with blockchain infrastructure, according to people briefed on the negotiations.", "fake", "crypto"),
    ("Sources within the {agency} indicate that regulators are preparing to grant {company} a full banking license, allowing it to offer FDIC-insured crypto deposit accounts.", "fake", "crypto"),

    # Crypto — fabricated market-moving events
    ("{company} CEO confirmed in a private investor call that the firm will allocate ${amount}B toward {coin} acquisitions over the next quarter, according to attendees.", "fake", "crypto"),
    ("Whale activity on the {coin} network suggests that large holders are accumulating positions ahead of a major partnership announcement expected next week, on-chain data reveals.", "fake", "crypto"),
    ("Developers on the {coin} network have quietly implemented a supply cap mechanism that would permanently limit circulation to {supply}M tokens, according to a leaked governance proposal.", "fake", "crypto"),

    # Finance — fabricated policy / economic events
    ("The Federal Reserve is reportedly considering an emergency rate cut of {basis} basis points, according to a leaked internal memo from the Federal Open Market Committee.", "fake", "finance"),
    ("Sources familiar with the matter indicate that the {agency} is preparing to halt all trading of {company} shares pending an investigation into accounting irregularities.", "fake", "finance"),
    ("{company} is set to announce bankruptcy proceedings as early as next week, according to insiders who spoke on condition of anonymity. The filing would be one of the largest in the sector.", "fake", "finance"),
    ("Internal communications obtained by reporters suggest that {country}'s central bank has depleted over {pct}% of its foreign reserves and may seek an IMF bailout within months.", "fake", "finance"),
    ("{company} CFO has been subpoenaed by the {agency} regarding alleged manipulation of {coin} futures contracts, according to three people familiar with the investigation.", "fake", "crypto"),

    # Finance — fabricated market manipulation
    ("Several hedge funds are reportedly coordinating a short squeeze on {company} shares, with combined short positions exceeding ${amount}B, according to institutional data.", "fake", "finance"),
    ("Trading in {coin} derivatives on {exchange} was temporarily halted after unusual activity suggested possible market manipulation by a single entity controlling over {pct}% of open interest.", "fake", "crypto"),

    # Crypto — fabricated regulatory bans / approvals
    ("The {agency} has privately informed major exchanges that it intends to delist all {coin} trading pairs within 30 days, according to two sources briefed on the matter.", "fake", "crypto"),
    ("Regulators in {country} have drafted legislation that would classify {coin} holders as unlicensed securities dealers, subjecting them to retroactive tax assessments.", "fake", "crypto"),
]

FILL = {
    "action": ["surged", "climbed", "rose", "gained", "rallied", "dropped", "fell", "declined", "edged", "slipped"],
    "pct": [str(round(random.uniform(0.5, 12.0), 1)) for _ in range(20)],
    "price": [str(round(random.uniform(35000, 95000), 2)) for _ in range(20)],
    "date": ["Tuesday", "Wednesday", "Thursday", "Friday", "Monday morning"],
    "reason": ["renewed institutional interest", "positive regulatory developments", "ETF inflow data", "macroeconomic shifts", "liquidation events in the derivatives market", "strong on-chain metrics"],
    "vol": [str(round(random.uniform(15, 85), 1)) for _ in range(10)],
    "event": ["Shapella", "Dencun", "Merge", "Proto-Danksharding", "Pectra"],
    "eth_price": [str(round(random.uniform(2000, 5000), 2)) for _ in range(10)],
    "company": ["BlackRock", "Fidelity", "Coinbase", "MicroStrategy", "JPMorgan", "Goldman Sachs", "Binance", "Kraken", "PayPal", "Morgan Stanley", "Citi", "Robinhood"],
    "partner": ["Microsoft", "Amazon Web Services", "Google Cloud", "IBM", "Deloitte", "Accenture"],
    "fund_type": ["spot Bitcoin ETF", "futures-based crypto fund", "digital asset trust"],
    "exchange": ["Coinbase", "Binance", "Kraken", "Gemini", "OKX"],
    "coin": ["Bitcoin", "Ethereum", "Solana", "Cardano", "XRP", "Dogecoin", "Polkadot", "Avalanche", "Chainlink"],
    "coin_price": [str(round(random.uniform(0.5, 250), 2)) for _ in range(15)],
    "basis": ["25", "50", "75", "100"],
    "rate_low": [str(round(random.uniform(4.5, 5.5), 2)) for _ in range(8)],
    "rate_high": [str(round(random.uniform(4.75, 5.75), 2)) for _ in range(8)],
    "quarter": ["1", "2", "3", "4"],
    "rev": [str(round(random.uniform(5, 80), 1)) for _ in range(10)],
    "rev_est": [str(round(random.uniform(4.5, 78), 1)) for _ in range(10)],
    "yoy_change": [str(round(random.uniform(3, 25), 1)) for _ in range(10)],
    "opr": ["2.75", "3.00", "3.25"],
    "growth": [str(round(random.uniform(2.5, 4.5), 1)) for _ in range(8)],
    "year": ["2025", "2026", "2027"],
    "series": ["A", "B", "C", "D"],
    "amount": [str(random.randint(10, 500)) for _ in range(15)],
    "valuation": [str(round(random.uniform(1, 50), 1)) for _ in range(10)],
    "investor": ["Sequoia Capital", "Andreessen Horowitz", "Tiger Global", "SoftBank", "Lightspeed Venture Partners"],
    "btc_amount": [str(random.randint(1000, 50000)) for _ in range(10)],
    "country": ["Singapore", "Switzerland", "Japan", "South Korea", "Brazil", "El Salvador", "the UAE"],
    "cbdc_type": ["wholesale CBDC", "retail digital currency", "central bank digital currency"],
    "trial_month": ["Q1", "Q2", "Q3", "the second half of the year"],
    "precedent_country": ["El Salvador's", "Singapore's", "the UAE's"],
    "gold_price": [str(round(random.uniform(1800, 2800), 2)) for _ in range(10)],
    "oil_price": [str(round(random.uniform(65, 120), 2)) for _ in range(10)],
    "barrels": [str(round(random.uniform(0.5, 2.0), 1)) for _ in range(8)],
    "prod_action": ["cut", "increase"],
    "region": ["the Middle East", "Eastern Europe", "the Asia-Pacific", "the South China Sea"],
    "agency": ["SEC", "CFTC", "Treasury Department", "Federal Reserve", "Justice Department", "Commodity Futures Trading Commission"],
    "target_company": ["a major crypto exchange", "a blockchain analytics firm", "a digital asset custody provider"],
    "supply": [str(random.randint(10, 100)) for _ in range(8)],
}


def fill_template(tpl):
    """Fills a template string with random values."""
    import re
    fields = {}
    raw = tpl[0]
    placeholders = re.findall(r"\{(\w+)\}", raw)
    for key in placeholders:
        fields[key] = random.choice(FILL.get(key, ["unknown"]))
    text = raw.format(**fields)
    return {"text": text, "label": tpl[1], "category": tpl[2], "source": "test", "language": "en"}


def main():
    rows = []

    # Generate REAL samples — roughly 50% crypto, 50% finance
    real_count_target = 250
    real_crypto = [t for t in REAL_TEMPLATES if t[2] == "crypto"]
    real_finance = [t for t in REAL_TEMPLATES if t[2] == "finance"]
    for i in range(real_count_target):
        pool = real_crypto if i % 2 == 0 else real_finance
        rows.append(fill_template(random.choice(pool)))

    # Generate FAKE samples — plausible misinformation
    fake_count_target = 250
    fake_crypto = [t for t in FAKE_TEMPLATES if t[2] == "crypto"]
    fake_finance = [t for t in FAKE_TEMPLATES if t[2] == "finance"]
    for i in range(fake_count_target):
        pool = fake_crypto if i % 2 == 0 else fake_finance
        rows.append(fill_template(random.choice(pool)))

    random.shuffle(rows)

    os.makedirs("evaluation", exist_ok=True)
    output_path = os.path.join("evaluation", "crypto_finance_testset.csv")

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label", "category", "source", "language"])
        writer.writeheader()
        writer.writerows(rows)

    real_n = sum(1 for r in rows if r["label"] == "real")
    fake_n = sum(1 for r in rows if r["label"] == "fake")
    crypto_n = sum(1 for r in rows if r["category"] == "crypto")
    finance_n = sum(1 for r in rows if r["category"] == "finance")

    print(f"Dataset generated: {output_path}")
    print(f"Total rows: {len(rows)}")
    print(f"Real: {real_n} | Fake: {fake_n}")
    print(f"Crypto: {crypto_n} | Finance: {finance_n}")
    print(f"\nSample REAL rows:")
    for r in [x for x in rows if x["label"] == "real"][:3]:
        print(f"  {r['text'][:100]}...")
    print(f"\nSample FAKE rows:")
    for r in [x for x in rows if x["label"] == "fake"][:3]:
        print(f"  {r['text'][:100]}...")


if __name__ == "__main__":
    main()
