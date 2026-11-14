"""Indian sample day of meals and routine tips (synopsis Module 3).

Deterministic and rule-based, like the rest of the diet engine. Built from
three answers the user gives on the Diet & Lifestyle questionnaire:

- occupation_type: the shape of their day (student, working professional,
  night shift, homemaker, physical work, retired). Decides meal times and
  routine tips.
- diet_preference: vegetarian, eggetarian, non-vegetarian, vegan or Jain.
  Decides the protein foods named, and Jain plans leave out onion, garlic
  and root vegetables.
- cuisine_region: north, south, east, west or mixed. Decides the staples
  (roti, rice, bhakri, idli and so on) so the plan looks like food the
  user already eats.

Health flags from the main engine then adjust portions and swaps (for
example millets in place of white rice when blood sugar is a concern).
These are general food suggestions, not medical nutrition therapy.
"""
from typing import Any, Dict, List, Optional

OCCUPATION_LABELS = {
    "student": "Student",
    "working_professional": "Working professional",
    "night_shift": "Night or rotating shift worker",
    "homemaker": "Homemaker",
    "physical_work": "Physically active job",
    "retired": "Retired",
}
DIET_LABELS = {
    "vegetarian": "Vegetarian",
    "eggetarian": "Vegetarian + eggs",
    "non_vegetarian": "Non-vegetarian",
    "vegan": "Vegan",
    "jain": "Jain",
}
REGION_LABELS = {
    "north": "North Indian",
    "south": "South Indian",
    "east": "East Indian",
    "west": "West Indian",
    "mixed": "Mixed Indian",
}

# ── Meal times by the shape of the day ──────────────────────────────────────
_DAY_SLOTS = [
    ("early", "On waking", "7:00 am"),
    ("breakfast", "Breakfast", "8:00 am"),
    ("mid_morning", "Mid-morning", "11:00 am"),
    ("lunch", "Lunch", "1:30 pm"),
    ("evening", "Evening snack", "5:00 pm"),
    ("dinner", "Dinner", "8:00 pm"),
]
_SLOTS = {
    "student": [
        ("early", "On waking", "6:30 am"),
        ("breakfast", "Breakfast before class", "7:30 am"),
        ("mid_morning", "Short break", "11:00 am"),
        ("lunch", "Lunch (tiffin or canteen)", "1:00 pm"),
        ("evening", "Study-time snack", "5:30 pm"),
        ("dinner", "Dinner", "8:30 pm"),
    ],
    # Assumes a shift of roughly 10 pm to 6 am; the plan says so.
    "night_shift": [
        ("early", "After waking", "1:30 pm"),
        ("lunch", "Main meal", "2:30 pm"),
        ("evening", "Evening snack", "6:30 pm"),
        ("dinner", "Before your shift", "9:00 pm"),
        ("shift", "During the shift", "2:00 am"),
        ("after_shift", "After the shift, before sleep", "6:30 am"),
    ],
}

_SCHEDULE_NOTES = {
    "night_shift": "Times assume a shift of about 10 pm to 6 am. Move them to match your own shift, keeping the same order.",
    "student": "Built around a college or school day. On holidays, keep the same meal order.",
}


def _protein(pref: Optional[str]) -> Dict[str, str]:
    """Protein foods to name, by food preference. Unknown preference stays
    vegetarian-safe and mentions eggs or fish only as an option."""
    table = {
        "vegetarian": {
            "breakfast": "a glass of milk or a bowl of curd",
            "meal": "a bowl of dal (moong, masoor, toor or chana), or rajma or chole",
            "extra": "50 to 75 g of paneer a few times a week",
            "snack": "sprouts chaat or roasted chana",
        },
        "eggetarian": {
            "breakfast": "1 to 2 boiled eggs or an egg bhurji with little oil",
            "meal": "a bowl of dal, rajma or chole, or an egg curry",
            "extra": "eggs or 50 to 75 g of paneer",
            "snack": "a boiled egg or roasted chana",
        },
        "non_vegetarian": {
            "breakfast": "1 to 2 boiled eggs",
            "meal": "a bowl of dal, or a palm-sized portion of fish or skinless chicken curry (not fried)",
            "extra": "fish such as rohu, bangda (mackerel) or mathi (sardine) twice a week",
            "snack": "a boiled egg or roasted chana",
        },
        "vegan": {
            "breakfast": "a glass of soy milk or a handful of peanuts",
            "meal": "a bowl of dal, rajma or chole, or soya chunks",
            "extra": "tofu or soya chunks a few times a week",
            "snack": "roasted chana or a handful of peanuts",
        },
        "jain": {
            "breakfast": "a glass of milk or a bowl of curd",
            "meal": "a bowl of moong or toor dal, or chole",
            "extra": "50 to 75 g of paneer a few times a week",
            "snack": "roasted chana or makhana",
        },
    }
    return table.get(pref or "", {
        "breakfast": "a glass of milk, a bowl of curd, or eggs if you eat them",
        "meal": "a bowl of dal, or fish, chicken or eggs if you eat them",
        "extra": "paneer, eggs or fish a few times a week, as your diet allows",
        "snack": "roasted chana or sprouts chaat",
    })


def _staple(region: Optional[str], glucose: bool, light: bool = False) -> str:
    """The roti/rice part of a main meal."""
    if glucose:
        options = {
            "north": "2 multigrain or bajra/jowar rotis",
            "south": "3/4 cup of red or brown rice, or ragi mudde",
            "east": "3/4 cup of red or brown rice, or 2 multigrain rotis",
            "west": "2 jowar or bajra bhakri",
        }
        staple = options.get(region or "", "2 multigrain rotis or 3/4 cup of brown rice or millet")
    else:
        options = {
            "north": "2 whole-wheat rotis",
            "south": "1 cup of rice",
            "east": "1 cup of rice (parboiled or red rice is better)",
            "west": "2 bhakri or whole-wheat rotis",
        }
        staple = options.get(region or "", "2 whole-wheat rotis or 1 cup of rice")
    return f"{staple} (a slightly smaller portion than at lunch)" if light else staple


def _breakfast(region: Optional[str], glucose: bool, jain: bool) -> str:
    if glucose:
        options = {
            "north": "a moong dal or besan chilla with vegetables",
            "south": "2 idlis or a ragi dosa with extra sambar",
            "east": "vegetable oats upma or a moong dal chilla",
            "west": "2 multigrain methi theplas with curd",
        }
        dish = options.get(region or "", "a moong dal chilla or vegetable oats upma")
    else:
        options = {
            "north": "vegetable poha, a besan chilla or dalia upma",
            "south": "2 to 3 idlis or a plain dosa with sambar and chutney",
            "east": "chira (poha) with curd and fruit, or vegetable upma",
            "west": "poha, upma or 2 methi theplas with curd",
        }
        dish = options.get(region or "", "vegetable poha or upma, or 2 idlis with sambar")
    return f"{dish}, made without onion, garlic or potato" if jain else dish


def _sabzi(jain: bool) -> str:
    if jain:
        return "a bowl of sabzi made without onion, garlic or root vegetables, such as lauki, tori, bhindi or beans"
    return "a bowl of seasonal sabzi such as lauki, tori, bhindi, palak, methi or beans"


def _salad(jain: bool) -> str:
    return "a cucumber and tomato salad" if jain else "a plate of salad (cucumber, tomato, onion, carrot)"


def _fruit(glucose: bool) -> str:
    if glucose:
        return "1 guava, apple or orange, or a few jamun (small portion)"
    return "a seasonal fruit such as papaya, guava, banana, apple or orange"


def _chai(glucose: bool) -> str:
    return "chai or coffee without sugar" if glucose else "chai or coffee with little or no sugar"


def _water(physical: bool) -> str:
    return (
        "a large glass of water, and keep drinking through the day (3 litres or more on hot days)"
        if physical else "a glass of warm water"
    )


def build_daily_meal_plan(
    occupation_type: Optional[str] = None,
    diet_preference: Optional[str] = None,
    cuisine_region: Optional[str] = None,
    *,
    glucose_caution: bool = False,
    cardiac_caution: bool = False,
    liver_caution: bool = False,
    weight_loss: bool = False,
    underweight: bool = False,
) -> Dict[str, Any]:
    jain = diet_preference == "jain"
    physical = occupation_type == "physical_work"
    protein = _protein(diet_preference)
    slots = _SLOTS.get(occupation_type or "", _DAY_SLOTS)

    lunch_items = [_staple(cuisine_region, glucose_caution), protein["meal"], _sabzi(jain), _salad(jain)]
    if diet_preference == "vegan":
        lunch_items.append("a glass of plain buttermilk made with soy curd, or lemon water")
    else:
        lunch_items.append("a bowl of curd or a glass of buttermilk (chaas)")
    if underweight or physical:
        added_fat = "a spoonful of peanut chutney" if diet_preference == "vegan" else "1 teaspoon of ghee"
        lunch_items.append(f"an extra roti or a little more rice, with {added_fat}")

    dinner_items = [_staple(cuisine_region, glucose_caution, light=True), protein["meal"], _sabzi(jain)]
    if not jain:
        dinner_items.append("or a bowl of vegetable khichdi with curd instead of the above")

    snack_items = [protein["snack"], _chai(glucose_caution)]
    if not glucose_caution:
        snack_items.append("or a handful of makhana")

    content: Dict[str, Dict[str, Any]] = {
        "early": {
            "items": [_water(physical), "4 to 5 soaked almonds or 1 walnut"],
            "tip": None,
        },
        "breakfast": {
            "items": [_breakfast(cuisine_region, glucose_caution, jain), protein["breakfast"], _chai(glucose_caution)],
            "tip": "Don't skip breakfast. A protein-rich start keeps you full until lunch.",
        },
        "mid_morning": {
            "items": [_fruit(glucose_caution), "or a glass of buttermilk or coconut water"],
            "tip": None,
        },
        "lunch": {
            "items": lunch_items,
            "tip": "Fill half the plate with sabzi and salad, a quarter with dal or protein, and a quarter with roti or rice.",
        },
        "evening": {
            "items": snack_items,
            "tip": "Swap samosa, pakora, vada pav, biscuits and namkeen for these on most days.",
        },
        "dinner": {
            "items": dinner_items,
            "tip": "Eat dinner 2 to 3 hours before you sleep, and keep it lighter than lunch.",
        },
        "shift": {
            "items": [_fruit(glucose_caution), protein["snack"], "warm water or herbal tea"],
            "tip": "Keep this small. Heavy, fried or sugary food in the middle of the night is hard to digest.",
        },
        "after_shift": {
            "items": ["a small bowl of curd with fruit, or a glass of warm milk", "no tea or coffee now, so you can sleep"],
            "tip": "Eat lightly, then sleep in a dark, quiet room.",
        },
    }

    # Occupation-specific notes on particular meals.
    if occupation_type == "student":
        content["lunch"]["tip"] = "Pack a tiffin of roti-sabzi-dal when you can. In the canteen, pick thali, dal-rice or idli over fried items and instant noodles."
    elif occupation_type == "working_professional":
        content["lunch"]["tip"] = "Carry a home-cooked lunchbox most days. Eating out, choose roti, dal and sabzi or grilled dishes over fried and creamy ones."
    elif occupation_type == "night_shift":
        content["lunch"]["tip"] = "Make this your biggest meal of the day."
        content["dinner"]["tip"] = "Eat a proper meal before the shift so you aren't hungry at 2 am."

    meals: List[Dict[str, Any]] = []
    for key, label, time in slots:
        entry = content[key]
        meals.append({"slot": label, "time": time, "items": entry["items"], "tip": entry["tip"]})

    # Health-specific swaps shown under the plan.
    swaps: List[str] = []
    if glucose_caution:
        swaps.append("Blood sugar: swap white rice and maida for millets (ragi, jowar, bajra), brown rice or multigrain atta, and skip sugar in chai and sweets.")
    if cardiac_caution:
        swaps.append("Blood pressure and heart: cook with less salt and skip achar, papad and packaged namkeen. Use mustard, groundnut or rice-bran oil sparingly, and limit ghee and vanaspati.")
    if liver_caution:
        swaps.append("Liver: avoid alcohol and deep-fried food (puri, bhature, pakora), and cut down on sweets and sugary drinks.")
    if weight_loss:
        swaps.append("Weight: use a smaller plate, have one roti or rice portion less, and avoid second helpings and late-night snacking.")
    if underweight:
        added_fat = "peanut butter or til" if diet_preference == "vegan" else "a teaspoon of ghee"
        swaps.append(f"Gaining weight: eat 5 to 6 times a day and add peanut chikki, nuts, banana and {added_fat} to meals.")

    return {
        "plan_for": {
            "occupation": OCCUPATION_LABELS.get(occupation_type or ""),
            "diet": DIET_LABELS.get(diet_preference or ""),
            "region": REGION_LABELS.get(cuisine_region or ""),
        },
        "schedule_note": _SCHEDULE_NOTES.get(occupation_type or ""),
        "meals": meals,
        "swaps": swaps,
    }


_ROUTINE_TIPS = {
    "student": [
        "Don't skip breakfast before college. Keep fruit or roasted chana in your bag for breaks instead of chips and cold drinks.",
        "Stand up and stretch every 45 to 60 minutes of study, and follow the 20-20-20 rule: every 20 minutes, look at something 20 feet away for 20 seconds.",
        "Aim for 7 to 9 hours of sleep, even in exam season. Late-night cramming on energy drinks or extra chai upsets sleep and memory.",
        "If exam stress or low mood feels too much, talk to someone you trust, or call Tele-MANAS on 14416 (free, 24x7).",
    ],
    "working_professional": [
        "Get up and walk for 3 to 5 minutes every hour, and take phone calls standing or walking.",
        "Keep your screen at eye level and follow the 20-20-20 rule to rest your eyes.",
        "Limit chai or coffee to 2 to 3 cups a day, with none after about 4 pm.",
        "Use your commute: take the stairs, or get off one stop early and walk.",
    ],
    "night_shift": [
        "Keep the same sleep window every day, even on days off, in a dark, quiet room. Blackout curtains or an eye mask help.",
        "Stop tea and coffee 4 to 5 hours before your shift ends so you can sleep afterwards.",
        "Get some daylight soon after you wake up, and a short walk before your shift.",
        "Night work raises the long-term risk of weight gain and high blood sugar, so a yearly health check is especially worthwhile.",
    ],
    "homemaker": [
        "Eat your own meals on time, rather than skipping lunch on busy days or finishing leftovers.",
        "Housework alone is often not enough exercise. Set aside 30 minutes for a walk or yoga.",
        "Include calcium (curd, milk, ragi, til) and iron (palak, chana, rajma) foods every day, with a vitamin C fruit such as guava or orange to help absorb iron.",
        "Keep fried snacks and sweets for occasions rather than everyday tea-time.",
    ],
    "physical_work": [
        "Your body needs more food and water than a desk job: eat proper meals, not just tea and biscuits, and drink water every hour.",
        "On hot days, have ORS, buttermilk or lemon water during breaks, rest in the shade, and stop if you feel dizzy or confused.",
        "Stretch before and after work, and lift with your knees, not your back.",
        "Get 7 to 8 hours of sleep so your muscles can recover.",
    ],
    "retired": [
        "Include protein at every meal (dal, curd, paneer, or eggs or fish if you eat them) to keep your muscles strong.",
        "Get calcium and vitamin D: milk or curd every day, and 15 to 20 minutes of morning sunlight.",
        "Drink water regularly even when you don't feel thirsty, since thirst weakens with age.",
        "Keep your medicine schedule somewhere visible, and take each medicine with meals only if your doctor advised it.",
    ],
}

_EXERCISE_TIMING = {
    "student": "Fit activity around classes: walk or cycle to college, or play a sport in the evening.",
    "working_professional": "Exercise before work, or take a brisk walk after dinner. Two 15-minute walks count as much as one 30-minute walk.",
    "night_shift": "Exercise after you wake up or before your shift, not straight after the shift when you should be winding down to sleep.",
    "homemaker": "A morning walk or yoga before the household rush is easiest to keep up.",
    "physical_work": "Your work is already active, so on workdays focus on stretching and rest. Use days off for a relaxed walk.",
    "retired": "A morning walk in the park and gentle yoga suit most people. Walk with a friend if you can.",
}


def routine_tips(occupation_type: Optional[str]) -> List[str]:
    return list(_ROUTINE_TIPS.get(occupation_type or "", []))


def exercise_timing(occupation_type: Optional[str]) -> Optional[str]:
    return _EXERCISE_TIMING.get(occupation_type or "")
