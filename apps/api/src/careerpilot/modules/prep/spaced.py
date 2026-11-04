from datetime import date, timedelta

# Review again sooner when you are less sure: confidence 1..5 maps to days until the next review.
INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}


def next_review(confidence: int, reviewed_on: date) -> date:
    return reviewed_on + timedelta(days=INTERVAL_DAYS[confidence])
