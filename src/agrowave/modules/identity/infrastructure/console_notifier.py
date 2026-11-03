"""Console notifier adapter for development environment (ADR-05)."""

import logging

from agrowave.modules.identity.domain.ports import Notifier

logger = logging.getLogger("agrowave.identity.notifier")


class ConsoleNotifier(Notifier):
    """Adapter printing transaction emails to standard output / logger."""

    def __init__(self, frontend_base_url: str = "http://localhost:5173") -> None:
        """Initializes the notifier with frontend base URL.

        Args:
            frontend_base_url: Base URL for web client links.
        """
        self._frontend_base_url = frontend_base_url.rstrip("/")

    def send_confirmation_email(self, to_email: str, token: str) -> None:
        """Logs the confirmation email link to stdout.

        Args:
            to_email: Recipient address.
            token: Verification token.
        """
        link = f"{self._frontend_base_url}/confirm-email/{token}"
        message = (
            "\n==================== [EMAIL: CONFIRM ACCOUNT] ====================\n"
            f"To: {to_email}\n"
            "Subject: Confirma tu cuenta en AGROWAVE\n\n"
            "Haz clic en el siguiente enlace para activar tu cuenta:\n"
            f"{link}\n"
            "===================================================================\n"
        )
        print(message, flush=True)
        logger.info("%s", message)

    def send_password_reset_email(self, to_email: str, token: str) -> None:
        """Logs the password reset link to stdout.

        Args:
            to_email: Recipient address.
            token: Verification token.
        """
        link = f"{self._frontend_base_url}/reset-password/{token}"
        message = (
            "\n================== [EMAIL: RESET PASSWORD] ==================\n"
            f"To: {to_email}\n"
            "Subject: Restablecer contrasena en AGROWAVE\n\n"
            "Haz clic en el siguiente enlace para restablecer tu contrasena:\n"
            f"{link}\n"
            "===============================================================\n"
        )
        print(message, flush=True)
        logger.info("%s", message)
