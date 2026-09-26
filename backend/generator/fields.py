"""Where each value is written on page 1 of the template (PDF points), and where the checkboxes are."""

import pymupdf

A_RIGHT, B_LEFT = (
    185,
    430,
)  # column edges: A writes left to right after its French label, B right-aligned against its Arabic label


HEADER = {  # name: box (left-aligned)
    "date": (90, 77, 135, 88),
    "time": (168, 77, 212, 88),
    "place": (58, 90, 300, 101),
    "phone_a": (75, 133, 300, 144),
}
PHONE_B = (B_LEFT, 133, 548, 144)  # Arabic side of the same line, right-aligned

# "Dégâts matériels autres qu'aux véhicules A et B": French-side and Arabic-side yes/no cells; the driver marks both groups alike
OTHER_DAMAGE = {
    True: [(236, 105.5, 250.5, 116.5), (397.5, 105.5, 412.5, 116.5)],
    False: [(288.5, 105.5, 303, 116.5), (348.5, 105.5, 363, 116.5)],
}


# name: (box for vehicle A, box for vehicle B). Lines sit at different heights in the two columns.
def line(a_y, a_x0, b_y, b_x1):
    return (a_x0, a_y[0], A_RIGHT, a_y[1]), (B_LEFT, b_y[0], b_x1, b_y[1])


VEHICLE = {
    "model": line((170, 182), 70, (172, 182), 548),
    "make": line((190, 200), 67, (191, 201), 542),
    "plate": line((202, 212), 130, (203, 213), 491),
    "coming_from": line((213, 223), 55, (215, 225), 543),
    "going_to": line((224, 234), 57, (227, 237), 539),
    "insured_last_name": line((260, 270), 39, (264, 274), 487),
    "insured_first_name": line((279, 289), 48, (276, 286), 530),
    "insured_address": line((290, 300), 49, (288, 298), 553),
    "insurer": line((301, 311), 78, (300, 310), 536),
    "attestation_no": line((312, 322), 78, (312, 322), 540),
    "policy_no": line((323, 333), 65, (324, 334), 544),
    "valid_from": ((92, 346, 127, 357), (488, 348, 524, 358)),
    "valid_to": ((140, 346, 185, 357), (432, 348, 473, 358)),
    "agency": line((364, 375), 49, (359, 369), 508),
    "driver_last_name": line((402, 412), 39, (398, 408), 487),
    "driver_first_name": line((421, 431), 48, (410, 420), 530),
    "driver_address": line((432, 442), 49, (422, 432), 553),
    "license_no": line((444, 454), 100, (434, 444), 521),
    "license_issued": line((466, 477), 54, (458, 468), 541),
    "license_prefecture": line((476, 486), 86, (467, 477), 547),
    "license_valid_until": line((487, 497), 97, (479, 489), 518),
}

DAMAGE = (
    (21, 626, A_RIGHT, 650),
    (B_LEFT, 621, 574, 633),
)  # A has room for two lines, B for one

# centre (x, y) of each licence category letter, in the order of CATEGORIES; the driver circles the right one
CATEGORIES = ["A1", "A", "B", "C", "D", "E", "F"]
CATEGORY_CENTRES = (
    [(x, 459) for x in (27, 38, 49, 60.5, 71.5, 83, 94)],
    [(x, 449) for x in (568.5, 557.5, 546, 534.5, 523.5, 512.5, 501)],
)


def checkboxes(page):
    """23 circumstance squares per vehicle (top to bottom) and the two tick-count boxes, read from the template."""
    d = page.get_drawings()
    squares = {
        tuple(round(v) for v in x["rect"])
        for x in d
        if x["type"] == "fs" and 6 < x["rect"].width < 9 and 6 < x["rect"].height < 9
    }
    left, right = (
        [r for r in sorted(squares, key=lambda r: r[1]) if pred(r)]
        for pred in (lambda r: r[0] < 300, lambda r: r[0] > 300)
    )
    counts = sorted(
        {
            tuple(round(v) for v in x["rect"])
            for x in d
            if x["type"] == "f"
            and x["fill"] == (1.0, 1.0, 1.0)
            and 9 < x["rect"].width < 11
            and 10 < x["rect"].height < 12
        }
    )
    assert len(left) == len(right) == 23 and len(counts) == 2, (
        len(left),
        len(right),
        counts,
    )
    return (left, right), counts
