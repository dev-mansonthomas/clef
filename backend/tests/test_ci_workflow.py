"""Garde sur le workflow CI.

Constat H1 de `docs/TODO.md` : `deploy-dev` n'avait aucun `needs:` et les jobs de
test étaient conditionnés `pull_request`. Sur un push vers `main`, les tests ne
s'exécutaient donc **même pas**, et le déploiement partait quand même. Seule une
protection de branche côté GitHub — hors du dépôt, donc invérifiable ici — pouvait
l'empêcher.

Ces assertions rendent la régression détectable dans le dépôt lui-même. Il n'existe
pas d'`actionlint` dans la VM : lire le YAML est la seule vérification honnête
disponible localement.
"""
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML requis pour lire le workflow CI")

WORKFLOW = (
    Path(__file__).resolve().parent.parent.parent
    / ".github" / "workflows" / "ci.yml"
)

#: Jobs qui doivent garder le déploiement.
TEST_JOBS = {"backend-test", "frontend-build", "frontend-test", "e2e"}


@pytest.fixture(scope="module")
def workflow() -> dict:
    assert WORKFLOW.is_file(), f"Workflow introuvable : {WORKFLOW}"
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def jobs(workflow) -> dict:
    return workflow["jobs"]


def _step_with(job: dict, needle: str) -> dict | None:
    """Retourne la première étape dont le `uses` contient `needle`."""
    for step in job.get("steps", []):
        if needle in str(step.get("uses", "")):
            return step
    return None


def test_all_test_jobs_exist(jobs):
    """Les quatre suites ont chacune un job."""
    missing = TEST_JOBS - set(jobs)
    assert not missing, f"Jobs de test absents du workflow : {sorted(missing)}"


def test_deploy_is_gated_by_every_test_job(jobs):
    """`deploy-dev` ne peut pas partir sans que les tests aient réussi."""
    needs = jobs["deploy-dev"].get("needs")
    assert needs, (
        "deploy-dev n'a aucun `needs:` — un push sur main déploierait sans test "
        "(docs/TODO.md H1)."
    )
    declared = set(needs if isinstance(needs, list) else [needs])
    missing = TEST_JOBS - declared
    assert not missing, f"deploy-dev ne dépend pas de : {sorted(missing)}"


def test_test_jobs_run_on_push_too(jobs):
    """Aucun job de test n'est restreint aux seules pull requests.

    C'est la moitié du bug H1 : un `if: github.event_name == 'pull_request'` sur
    les jobs de test les rend inertes sur `push`, ce qui vide le `needs:` de son
    sens.
    """
    for name in sorted(TEST_JOBS):
        condition = str(jobs[name].get("if", ""))
        assert "pull_request" not in condition, (
            f"Le job {name} est conditionné `{condition}` : il ne tournerait pas "
            "sur un push vers main."
        )


def test_backend_job_provides_a_redis_service(jobs):
    """Le job backend fournit un Redis 8 réel.

    Sans lui, les 16 tests marqués `integration` sont ignorés et la CI devient
    aveugle au chemin de données réel.
    """
    services = jobs["backend-test"].get("services", {})
    assert "redis" in services, (
        "Le job backend-test ne déclare aucun service `redis` : les tests "
        "`integration` seraient tous ignorés."
    )
    image = services["redis"]["image"]
    assert image.startswith("redis:8"), (
        f"Service redis en image {image!r} ; Redis 8 attendu "
        "(RedisJSON est une dépendance dure)."
    )


def test_backend_job_pins_python_314(jobs):
    """La CI épingle la version exigée par `backend/pyproject.toml`."""
    step = _step_with(jobs["backend-test"], "actions/setup-python")
    assert step, "Aucune étape actions/setup-python dans backend-test"
    assert str(step["with"]["python-version"]) == "3.14", (
        f"CI en Python {step['with']['python-version']}, projet en >=3.14"
    )


@pytest.mark.parametrize("job_name", ["frontend-build", "frontend-test", "e2e"])
def test_frontend_jobs_pin_node_24(jobs, job_name):
    """Les jobs frontend épinglent Node 24, comme les Dockerfiles et la VM."""
    step = _step_with(jobs[job_name], "actions/setup-node")
    assert step, f"Aucune étape actions/setup-node dans {job_name}"
    assert str(step["with"]["node-version"]) == "24", (
        f"{job_name} en Node {step['with']['node-version']}, attendu 24"
    )
