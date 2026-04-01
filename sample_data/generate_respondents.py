"""Generate synthetic respondent data for Insight-Engine testing.

Creates 300 rows with realistic correlations between demographics, attitudes,
behaviors, and outcomes for testing segmentation and analysis blocks.
"""
import csv
import random
import math
from pathlib import Path

# Set seed for reproducibility
random.seed(42)

# Configuration
N = 300
OUTPUT_PATH = Path("sample_data/respondents_300.csv")

# Define value pools
REGIONS = ["Northeast", "Southeast", "Midwest", "Southwest", "West"]
EDUCATION_LEVELS = ["High School", "Some College", "Bachelor's", "Graduate Degree"]
INCOME_BRACKETS = ["< $25k", "$25k-$50k", "$50k-$75k", "$75k-$100k", "$100k-$150k", "> $150k"]
GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"]
URBAN_RURAL = ["Urban", "Suburban", "Rural"]

CATEGORIES = ["Electronics", "Fashion", "Home & Garden", "Sports", "Health & Beauty", "Food & Beverage"]
FREQUENCIES = ["Weekly", "Bi-weekly", "Monthly", "Quarterly", "Rarely"]
CHANNELS = ["Online", "In-store", "Mobile App", "Social Commerce", "Marketplace"]
BRANDS = ["Brand A", "Brand B", "Brand C", "Brand D", "Brand E"]

def normal_random(mean, std):
    """Box-Muller transform for normal distribution (no numpy)."""
    u1 = random.random()
    u2 = random.random()
    z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mean + std * z0

def generate_attitudes(segment_type):
    """Generate attitudinal scores based on underlying segment persona."""
    base = {
        "price_importance": normal_random(4, 1.5),
        "quality_importance": normal_random(4, 1.5),
        "convenience_importance": normal_random(4, 1.5),
        "sustainability_importance": normal_random(4, 1.5),
        "brand_loyalty": normal_random(4, 1.5),
    }

    # Adjust based on segment type
    adjustments = {
        "Price Conscious": {"price_importance": 2.5, "quality_importance": -0.5, "brand_loyalty": -1.0},
        "Quality Seeker": {"quality_importance": 2.0, "price_importance": -0.5, "brand_loyalty": 0.5},
        "Convenience First": {"convenience_importance": 2.0, "price_importance": 0.5, "sustainability_importance": -0.5},
        "Eco Advocate": {"sustainability_importance": 2.5, "price_importance": -0.5, "quality_importance": 0.5},
        "Brand Loyalist": {"brand_loyalty": 2.0, "price_importance": -0.5, "quality_importance": 0.5},
    }

    adj = adjustments.get(segment_type, {})
    for key, delta in adj.items():
        base[key] += delta

    # Clamp to 1-7 scale and round
    for key in base:
        base[key] = max(1, min(7, round(base[key])))

    return base

def generate_outcomes(attitudes, segment_type):
    """Generate outcome metrics correlated with attitudes."""
    # Base satisfaction influenced by attitude alignment
    base_satisfaction = 5.0
    base_satisfaction += (attitudes["quality_importance"] - 4) * 0.3
    base_satisfaction += (attitudes["convenience_importance"] - 4) * 0.2

    # Segment-specific adjustments
    segment_satisfaction = {
        "Price Conscious": -0.5 if attitudes["price_importance"] < 5 else 0.5,
        "Quality Seeker": 0.5 if attitudes["quality_importance"] > 5 else -0.5,
        "Convenience First": 0.5 if attitudes["convenience_importance"] > 5 else -0.5,
        "Eco Advocate": 0.3 if attitudes["sustainability_importance"] > 5 else -0.3,
        "Brand Loyalist": 0.4 if attitudes["brand_loyalty"] > 5 else -0.4,
    }

    base_satisfaction += segment_satisfaction.get(segment_type, 0)
    satisfaction = max(1, min(10, round(normal_random(base_satisfaction, 1.5))))

    # NPS correlates with satisfaction
    nps_base = (satisfaction - 5) * 0.8 + 5
    nps = max(0, min(10, round(normal_random(nps_base, 1.2))))

    # Would recommend based on NPS thresholds
    would_recommend = "Yes" if nps >= 7 else ("Maybe" if nps >= 5 else "No")

    return {
        "satisfaction_score": satisfaction,
        "nps_likelihood": nps,
        "would_recommend": would_recommend,
    }

def generate_behavior(segment_type, attitudes):
    """Generate behavioral data aligned with attitudes."""
    # Category preference by segment
    category_by_segment = {
        "Price Conscious": ["Food & Beverage", "Electronics", "Fashion"],
        "Quality Seeker": ["Electronics", "Health & Beauty", "Home & Garden"],
        "Convenience First": ["Food & Beverage", "Sports", "Electronics"],
        "Eco Advocate": ["Health & Beauty", "Home & Garden", "Fashion"],
        "Brand Loyalist": ["Fashion", "Electronics", "Sports"],
    }

    preferred_cats = category_by_segment.get(segment_type, CATEGORIES)
    primary_category = random.choice(preferred_cats)

    # Purchase frequency correlates with convenience importance
    freq_map = {7: "Weekly", 6: "Bi-weekly", 5: "Monthly", 4: "Monthly", 3: "Quarterly", 2: "Rarely", 1: "Rarely"}
    purchase_frequency = freq_map.get(attitudes["convenience_importance"], "Monthly")

    # Monthly spend correlates with income proxy (age + education) and price sensitivity
    base_spend = random.randint(50, 500)
    if attitudes["price_importance"] >= 6:
        base_spend = int(base_spend * 0.7)  # Price conscious spend less
    elif attitudes["quality_importance"] >= 6:
        base_spend = int(base_spend * 1.3)  # Quality seekers spend more

    # Channel preference by segment
    channel_by_segment = {
        "Price Conscious": ["Marketplace", "Online"],
        "Quality Seeker": ["In-store", "Online"],
        "Convenience First": ["Mobile App", "Online"],
        "Eco Advocate": ["Online", "Social Commerce"],
        "Brand Loyalist": ["In-store", "Mobile App"],
    }
    preferred_channels = channel_by_segment.get(segment_type, CHANNELS)
    channel_preference = random.choice(preferred_channels)

    # Brand loyalty
    brand_used = random.choice(BRANDS)

    return {
        "primary_category": primary_category,
        "purchase_frequency": purchase_frequency,
        "avg_monthly_spend": base_spend,
        "brand_used_most_often": brand_used,
        "channel_preference": channel_preference,
    }

def generate_demographics():
    """Generate demographic attributes."""
    # Age with realistic distribution (skewed toward 25-54)
    age = int(normal_random(38, 12))
    age = max(18, min(75, age))

    # Other demographics
    gender = random.choice(GENDERS)
    education = random.choice(EDUCATION_LEVELS)
    region = random.choice(REGIONS)
    urban_rural = random.choices(URBAN_RURAL, weights=[0.4, 0.4, 0.2])[0]
    household_size = random.choices([1, 2, 3, 4, 5], weights=[0.2, 0.3, 0.25, 0.15, 0.1])[0]

    # Income correlates with age and education
    income_idx = EDUCATION_LEVELS.index(education)
    base_income = income_idx + random.randint(0, 2)
    base_income = min(base_income, len(INCOME_BRACKETS) - 1)
    income_bracket = INCOME_BRACKETS[base_income]

    return {
        "age": age,
        "gender": gender,
        "education": education,
        "income_bracket": income_bracket,
        "region": region,
        "urban_rural": urban_rural,
        "household_size": household_size,
    }

def main():
    """Generate the synthetic dataset."""
    segments = ["Price Conscious", "Quality Seeker", "Convenience First", "Eco Advocate", "Brand Loyalist"]
    segment_weights = [0.25, 0.20, 0.20, 0.15, 0.20]

    rows = []
    for i in range(1, N + 1):
        # Assign segment (ground truth for validation)
        segment_type = random.choices(segments, weights=segment_weights)[0]

        # Generate correlated data
        demographics = generate_demographics()
        attitudes = generate_attitudes(segment_type)
        behaviors = generate_behavior(segment_type, attitudes)
        outcomes = generate_outcomes(attitudes, segment_type)

        row = {
            "respondent_id": f"R{str(i).zfill(4)}",
            **demographics,
            **behaviors,
            **attitudes,
            **outcomes,
            "segment_persona": segment_type,  # Ground truth for validation
        }
        rows.append(row)

    # Write CSV
    fieldnames = [
        "respondent_id",
        "age", "gender", "education", "income_bracket", "region",
        "urban_rural", "household_size",
        "primary_category", "purchase_frequency", "avg_monthly_spend",
        "brand_used_most_often", "channel_preference",
        "price_importance", "quality_importance", "convenience_importance",
        "sustainability_importance", "brand_loyalty",
        "satisfaction_score", "nps_likelihood", "would_recommend",
        "segment_persona",
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {N} respondents: {OUTPUT_PATH}")
    print("\nColumn categories:")
    print(f"  Demographics: {len([c for c in fieldnames if c in ['age', 'gender', 'education', 'income_bracket', 'region', 'urban_rural', 'household_size']])} columns")
    print(f"  Behavioral: {len([c for c in fieldnames if c in ['primary_category', 'purchase_frequency', 'avg_monthly_spend', 'brand_used_most_often', 'channel_preference']])} columns")
    print(f"  Attitudinal: {len([c for c in fieldnames if 'importance' in c or c == 'brand_loyalty'])} columns")
    print(f"  Outcome: {len([c for c in fieldnames if c in ['satisfaction_score', 'nps_likelihood', 'would_recommend']])} columns")
    print("  Ground truth: segment_persona")

if __name__ == "__main__":
    main()
