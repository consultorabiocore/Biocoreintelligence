from biocore.domain.ecological_evidence import EvidenceSource, TaxonomicGroup
from biocore.integrations.inaturalist import (
    INaturalistIdentifierError,
    observation_from_api,
    observation_id,
)

import pytest


def test_inaturalist_identifier_accepts_id_and_public_url() -> None:
    assert observation_id("12345") == "12345"
    assert (
        observation_id("https://www.inaturalist.org/observations/12345")
        == "12345"
    )
    with pytest.raises(INaturalistIdentifierError):
        observation_id("https://example.com/observations/12345")


def test_inaturalist_fixture_preserves_author_and_photo_license() -> None:
    result = observation_from_api(
        {
            "id": 12345,
            "uri": "https://www.inaturalist.org/observations/12345",
            "observed_on": "2026-07-02",
            "location": "-36.82,-73.03",
            "quality_grade": "research",
            "license_code": "cc-by-nc",
            "user": {"login": "loreto", "name": "Loreto Campos"},
            "taxon": {
                "name": "Cyttaria espinosae",
                "preferred_common_name": "Digueñe",
                "iconic_taxon_name": "Fungi",
            },
            "observation_photos": [
                {
                    "photo": {
                        "id": 8,
                        "original_url": "https://static.inaturalist.org/photo.jpg",
                        "license_code": "cc-by-nc",
                        "attribution": "(c) Loreto Campos, CC BY-NC",
                    }
                }
            ],
        }
    )

    assert result.external_id == "12345"
    assert result.observer_name == "Loreto Campos"
    assert result.taxonomic_group == TaxonomicGroup.FUNGA
    assert result.observation_license == "cc-by-nc"
    assert result.media[0].license == "cc-by-nc"
    assert result.media[0].metadata["reuse_copied"] is False
