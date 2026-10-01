"""Test-Runner, der die Testsuite grundsaetzlich vom echten OpenAI-Konto trennt.

Seit settings.py die lokale .env laedt, steht ein dort eingetragener echter
API-Schluessel auch waehrend "manage.py test" in den Settings. Ein Test, der eine
KI-Aktion ausloest und den Mock nicht selbst erzwingt, wuerde dann einen echten,
kostenpflichtigen Aufruf machen.

Der Runner setzt deshalb fuer den gesamten Lauf AI_MOCK_MODE=True und leert den
Schluessel. Tests, die den Nicht-Mock-Pfad pruefen, ueberschreiben das wie
bisher gezielt per @override_settings und patchen dabei das SDK.
"""

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class OfflineTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._ki_offline = override_settings(AI_MOCK_MODE=True, OPENAI_API_KEY="")
        self._ki_offline.enable()

    def teardown_test_environment(self, **kwargs):
        self._ki_offline.disable()
        super().teardown_test_environment(**kwargs)
