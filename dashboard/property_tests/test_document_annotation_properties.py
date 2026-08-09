import math
import random

from document_annotation import _valid_image_region


def test_valid_image_region_agrees_with_strict_bounds_for_broad_inputs():
    random_source = random.Random(20260808)

    for _ in range(1000):
        width = random_source.randint(1, 4000)
        height = random_source.randint(1, 4000)
        region = tuple(
            random_source.uniform(-max(width, height), 2 * max(width, height))
            for _ in range(4)
        )
        left, top, right, bottom = region
        expected = (
            all(math.isfinite(value) for value in region)
            and 0 <= left < right <= width
            and 0 <= top < bottom <= height
        )

        assert _valid_image_region(region, width, height) is expected


def test_valid_image_region_accepts_every_generated_interior_rectangle():
    random_source = random.Random(20260809)

    for _ in range(1000):
        width = random_source.randint(2, 4000)
        height = random_source.randint(2, 4000)
        left, right = sorted(random_source.sample(range(width + 1), 2))
        top, bottom = sorted(random_source.sample(range(height + 1), 2))

        assert _valid_image_region((left, top, right, bottom), width, height)
