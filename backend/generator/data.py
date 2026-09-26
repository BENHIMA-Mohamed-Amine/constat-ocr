"""Sample a fake constat record. Every value is invented; formats and cross-field rules follow real Moroccan ones."""

import math
import random
from datetime import date, timedelta

FIRST = [
    "Mohamed",
    "Ahmed",
    "Youssef",
    "Karim",
    "Rachid",
    "Hicham",
    "Omar",
    "Mehdi",
    "Khalid",
    "Hassan",
    "Amine",
    "Zakaria",
    "Fatima",
    "Khadija",
    "Samira",
    "Sara",
    "Meryem",
    "Nadia",
    "Latifa",
    "Imane",
    "Salma",
    "Hajar",
    "Abdelilah",
    "Nabil",
]
LAST = [
    "Benali",
    "El Amrani",
    "Alaoui",
    "Idrissi",
    "Tazi",
    "Bennani",
    "Fassi",
    "Berrada",
    "Lahlou",
    "Ouazzani",
    "Mansouri",
    "Benjelloun",
    "Chraibi",
    "Rifai",
    "Bouzid",
    "Saidi",
    "Naciri",
    "Skalli",
    "Mernissi",
    "Hamidi",
    "Belhaj",
    "Kabbaj",
    "Lamrani",
]
CITIES = [
    "Casablanca",
    "Rabat",
    "Meknes",
    "Fes",
    "Marrakech",
    "Tanger",
    "Agadir",
    "Kenitra",
    "Oujda",
    "Tetouan",
    "Sale",
    "Temara",
]
STREETS = [
    "Av. Mohammed V",
    "Bd Zerktouni",
    "Av. Hassan II",
    "Rue Allal Ben Abdellah",
    "Bd Anfa",
    "Av. des FAR",
    "Rue Tarfaya",
    "Bd Moulay Youssef",
    "Av. Mohammed VI",
    "Rue Ibn Sina",
    "Bd Al Massira",
    "Av. Al Qods",
]
DISTRICTS = [
    "Hay Salam",
    "Al Massira",
    "Hay Riad",
    "Agdal",
    "Maarif",
    "Ain Sebaa",
    "Bourgogne",
    "Hay Mohammadi",
    "Sidi Maarouf",
    "Lot Al Wifaq",
]
INSURERS = [
    "RMA",
    "WAFA ASSURANCE",
    "AXA ASSURANCE MAROC",
    "SAHAM ASSURANCE",
    "ATLANTASANAD",
    "ALLIANZ MAROC",
    "MAMDA",
    "SANLAM MAROC",
    "ZURICH MAROC",
]
CARS = {
    "Dacia": ["Logan", "Sandero", "Duster"],
    "Renault": ["Clio", "Megane", "Kangoo"],
    "Peugeot": ["208", "301", "308"],
    "Citroen": ["C3", "Berlingo"],
    "Hyundai": ["i10", "Accent"],
    "Kia": ["Picanto", "Rio"],
    "Fiat": ["Punto", "Tipo"],
    "Toyota": ["Yaris", "Corolla"],
    "Volkswagen": ["Golf", "Polo"],
    "Ford": ["Fiesta", "Focus"],
}
DAMAGE = [
    "Pare choc avant, phare droit",
    "Aile arriere gauche",
    "Portiere avant droite",
    "Pare choc arriere, coffre",
    "Calandre, capot",
    "Retroviseur gauche, aile avant",
    "Phare avant gauche, pare choc",
    "Portiere arriere droite, aile",
]
CATEGORY_WEIGHTS = {"B": 88, "A": 4, "A1": 2, "C": 3, "D": 1, "E": 1, "F": 1}
# accident scenarios: (ticks for A, ticks for B, plausible impact zones for A, for B)
# roles are swapped at random. Circumstance numbers 1-23 are those of the form.
F, FL, FR, R, RL, RR, L, RT = (
    "front",
    "front_left",
    "front_right",
    "rear",
    "rear_left",
    "rear_right",
    "left",
    "right",
)
SCENARIOS = [
    ([1], [], [F, FL, FR], [R, RL, RR]),
    ([9], [], [FR, FL], [L, RT]),
    ([8], [9], [L, RT, RL, RR], [F, FL, FR]),
    ([8], [11], [F, L, RT], [R, RL, RR]),
    ([10], [], [RL, RR, L, RT], [L, RT, FL, FR]),
    ([11], [], [R, RL, RR], [F, FL, FR]),
    ([12], [16], [FL, L], [L, RL]),
    ([14], [], [L, RT, FL, FR], [L, RT]),
    ([15], [], [FR, RT], [L, FL]),
    ([16], [19], [FL, L], [FL, F]),
    ([18], [], [FL, FR, F], [L, RT]),
    ([21], [5], [RT, FR], [FL, F]),
    ([21], [], [F, FL, FR], [L, RT, F]),
    ([22], [], [L, RT], [F, FL, FR]),
    ([23], [], [L, RT], [FL, FR, L, RT]),
    ([13], [], [L, RT, FL, FR], [L, RT]),
    ([6], [7], [FR, F], [L, FL]),
    ([17], [], [RT, L, FR], [L, RT]),
    ([20], [], [F, FL, FR], [F, FL, FR]),
]
VEHICLE_TYPES = {"car": 88, "moto": 5, "truck": 4, "tricycle": 2, "bus": 1}
MODELS = {
    "car": CARS,
    "moto": {
        "Yamaha": ["Tmax", "NMAX"],
        "Honda": ["PCX", "SH"],
        "Sym": ["Symphony"],
        "Peugeot": ["Kisbee"],
    },
    "tricycle": {"Piaggio": ["Ape"], "Bajaj": ["RE"]},
    "bus": {"Mercedes": ["Tourismo"], "Iveco": ["Daily"], "Irizar": ["i6"]},
    "truck": {
        "Renault": ["Master", "D Wide"],
        "Isuzu": ["NPR"],
        "Mercedes": ["Actros", "Atego"],
        "Volvo": ["FH"],
        "Iveco": ["Eurocargo"],
    },
}


def fmt(d):
    return d.strftime("%d/%m/%Y")


def add_years(d, n):
    return (
        d.replace(year=d.year + n, day=28)
        if d.month == 2 and d.day == 29
        else d.replace(year=d.year + n)
    )


def digits(rng, n):
    return "".join(rng.choice("0123456789") for _ in range(n))


def phone(rng):
    return f"0{rng.choice('67')}{digits(rng, 8)}"


def street(rng, city=None):
    return f"{rng.choice(STREETS)} {city or rng.choice(CITIES)}"


def vehicle(rng, accident, ticks, zone):
    vtype = rng.choices(list(VEHICLE_TYPES), list(VEHICLE_TYPES.values()))[0]
    make = rng.choice(list(MODELS[vtype]))
    valid_from = accident - timedelta(days=rng.randint(10, 350))
    issued = accident - timedelta(days=rng.randint(2 * 365, 30 * 365))
    valid_until = add_years(issued, 10)
    while valid_until <= accident:
        valid_until = add_years(valid_until, 5)
    city = rng.choice(CITIES)
    last = rng.choice(LAST)
    driver_first, driver_last = (
        (rng.choice(FIRST), rng.choice(LAST)) if rng.random() < 0.3 else (None, None)
    )  # sometimes not the insured
    insured_first = rng.choice(FIRST)
    return {
        "vehicle_type": vtype,
        "impact_zone": zone,
        "model": rng.choice(MODELS[vtype][make]),
        "make": make,
        "plate": f"{rng.randint(1, 99999)}-{rng.choice('ABDHJTW')}-{rng.randint(1, 89)}",
        "coming_from": rng.choice(STREETS),
        "going_to": rng.choice(STREETS),
        "insured_last_name": last.upper(),
        "insured_first_name": insured_first,
        "insured_address": f"{rng.choice(DISTRICTS)} {city}",
        "insurer": rng.choice(INSURERS),
        "attestation_no": f"{rng.randint(10, 99)}{rng.choice('AB')} {digits(rng, 9)}",
        "policy_no": digits(rng, rng.choice([12, 15])),
        "valid_from": fmt(valid_from),
        "valid_to": fmt(valid_from + timedelta(days=364)),
        "agency": f"{rng.choice(LAST).upper()} ASSURANCES"
        if rng.random() < 0.5
        else f"AGENCE {city.upper()} CENTRE",
        "driver_last_name": (driver_last or last).upper(),
        "driver_first_name": driver_first or insured_first,
        "driver_address": f"{rng.choice(DISTRICTS)} {city}",
        "license_no": f"{rng.randint(1, 99):02d}/{digits(rng, 6)}",
        "license_category": rng.choices(
            list(CATEGORY_WEIGHTS), list(CATEGORY_WEIGHTS.values())
        )[0],
        "license_issued": fmt(issued),
        "license_prefecture": city,
        "license_valid_until": fmt(valid_until),
        "damage": rng.choice(DAMAGE),
        "circumstances": ticks,
        "circumstance_count": len(ticks),
    }


CAR_LENGTH, CAR_WIDTH = 36, 16  # cars in the sketch, canvas pixels
CANVAS_SIZE = (
    240,
    120,
)  # sketch canvas in undistorted units (the template stretches its picture; the drawing is scaled back onto it)
CANVAS = (16, 3, 238, 117)  # usable road area
# where each impact zone sits on a car: x forward, y towards the driver's right
ZONE_DIR = {
    "front": (1, 0),
    "rear": (-1, 0),
    "left": (0, -1),
    "right": (0, 1),
    "front_left": (1, -1),
    "front_right": (1, 1),
    "rear_left": (-1, -1),
    "rear_right": (-1, 1),
}


def _rot(v, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return c * v[0] - s * v[1], s * v[0] + c * v[1]


def _contact(zone, deg):
    """Point on a car (relative to its centre) and outward direction of a zone, for a car heading `deg`."""
    d = ZONE_DIR[zone]
    return _rot((d[0] * CAR_LENGTH / 2, d[1] * CAR_WIDTH / 2), deg), _rot(
        (d[0] / math.hypot(*d), d[1] / math.hypot(*d)), deg
    )


def _fits(x, y, deg, pad=0):
    ex = (
        abs(math.cos(math.radians(deg))) * CAR_LENGTH / 2
        + abs(math.sin(math.radians(deg))) * CAR_WIDTH / 2
    )
    ey = (
        abs(math.sin(math.radians(deg))) * CAR_LENGTH / 2
        + abs(math.cos(math.radians(deg))) * CAR_WIDTH / 2
    )
    return (
        CANVAS[0] + pad <= x - ex
        and x + ex <= CANVAS[2] - pad
        and CANVAS[1] + pad <= y - ey
        and y + ey <= CANVAS[3] - pad
    )


LANE_Y = {
    0: 72,
    180: 46,
}  # right-hand traffic: cars heading right drive in the lower lane, cars heading left in the upper one
ROAD_Y = (36, 82)  # the main road's width on the canvas
STEM_DX = {
    90: -11,
    270: 11,
}  # side road: southbound traffic keeps to the west lane, northbound to the east lane


def sample_sketch(rng, zone_a, zone_b):
    """Place both cars so that A's damaged zone touches B's damaged zone. At the contact point the two outward
    directions are opposite, which fixes B's heading relative to A. If the cars end up roughly parallel the road is
    a two-way road with A in its lane; if roughly perpendicular it is a T-junction, with A on the main road and B
    on the side road, in the lane that matches B's heading. Centres in canvas units, heading in degrees (0 = right, 90 = down)."""
    _, na = _contact(zone_a, 0)
    _, nb = _contact(zone_b, 0)
    rel = (
        math.degrees(math.atan2(-na[1], -na[0]))
        - math.degrees(math.atan2(nb[1], nb[0]))
    ) % 360
    parallel = rel % 180 <= 45 or rel % 180 >= 135
    for attempt in range(500):
        lane = rng.choice([0, 180])
        ha, ay = lane + rng.uniform(-4, 4), LANE_Y[lane] + rng.uniform(-3, 3)
        hb = ha + rel + rng.uniform(-4, 4)
        (px, py), (nax, nay) = _contact(zone_a, ha)
        (qx, qy), _ = _contact(zone_b, hb)
        dx, dy = (
            px - qx - nax * 1.5,
            py - qy - nay * 1.5,
        )  # B's centre relative to A's; 1.5 px of overlap so the cars touch
        if parallel:
            ax, junction = rng.uniform(60, 180), None
        else:
            down = 90 if hb % 360 < 180 else 270
            xj = rng.uniform(80, 170)
            ax = xj + STEM_DX[down] - dx  # B lands in its lane of the side road
            junction = {"x": round(xj, 1), "side": "north" if down == 90 else "south"}
        on_road = (
            not parallel or ROAD_Y[0] <= ay + dy <= ROAD_Y[1] or attempt > 300
        )  # keep B on the road unless no placement allows it
        if (
            on_road and _fits(ax, ay, ha, pad=2) and _fits(ax + dx, ay + dy, hb, pad=2)
        ):  # margin survives the rounding of the stored pose
            break
    pose = lambda x, y, h: {
        "x": round(x, 1),
        "y": round(y, 1),
        "heading": round(h % 360, 1),
    }
    return {
        "layout": "two_way" if parallel else "t_junction",
        "junction": junction,
        "a": pose(ax, ay, ha),
        "b": pose(ax + dx, ay + dy, hb),
    }


def sample_record(rng: random.Random):
    accident = date(2022, 1, 1) + timedelta(days=rng.randint(0, 1700))
    a, b, zone_a, zone_b = rng.choice(SCENARIOS)
    if rng.random() < 0.5:
        a, b, zone_a, zone_b = b, a, zone_b, zone_a
    city = rng.choice(CITIES)
    va, vb = (
        vehicle(rng, accident, sorted(a), rng.choice(zone_a)),
        vehicle(rng, accident, sorted(b), rng.choice(zone_b)),
    )
    while vb["plate"] == va["plate"]:
        vb["plate"] = vehicle(rng, accident, [], "front")["plate"]
    return {
        "date": fmt(accident),
        "time": f"{rng.randint(6, 23):02d}h{rng.choice(range(0, 60, 5)):02d}",
        "place": street(rng, city),
        "phone_a": phone(rng),
        "phone_b": phone(rng),
        "other_damage": rng.random() < 0.08,
        "vehicle_a": va,
        "vehicle_b": vb,
        "sketch": sample_sketch(rng, va["impact_zone"], vb["impact_zone"]),
    }
