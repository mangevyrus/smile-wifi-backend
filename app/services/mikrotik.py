import secrets
import string

import routeros_api

from app.config import get_settings


class MikroTikError(Exception):
    """Raised when a MikroTik operation fails."""


class MikroTikService:
    """
    Service for communicating with the MikroTik RouterOS API.
    """

    def __init__(self):
        self.settings = get_settings()

    def _connect(self):
        try:
            connection = routeros_api.RouterOsApiPool(
                host=self.settings.mikrotik_host,
                username=self.settings.mikrotik_username,
                password=self.settings.mikrotik_password,
                port=self.settings.mikrotik_port,
                plaintext_login=True,
            )

            return connection

        except Exception as exc:
            raise MikroTikError(
                f"Failed to connect to MikroTik: {exc}"
            ) from exc

    @staticmethod
    def generate_username(prefix: str = "smile") -> str:
        """
        Generate a short random hotspot username.
        Example:
            smilea7k92m
        """

        alphabet = string.ascii_lowercase + string.digits

        random_part = "".join(
            secrets.choice(alphabet)
            for _ in range(8)
        )

        return f"{prefix}{random_part}"

    @staticmethod
    def generate_password(length: int = 8) -> str:
        """
        Generate a random hotspot password.
        """

        alphabet = (
            string.ascii_letters
            + string.digits
        )

        return "".join(
            secrets.choice(alphabet)
            for _ in range(length)
        )

    def get_hotspot_user(self, username: str):
        """
        Find a HotSpot user by username.
        Returns the RouterOS record or None.
        """

        connection = self._connect()

        try:
            api = connection.get_api()

            resource = api.get_resource(
                "/ip/hotspot/user"
            )

            users = resource.get(
                name=username
            )

            return users[0] if users else None

        except Exception as exc:
            raise MikroTikError(
                f"Failed to find HotSpot user '{username}': {exc}"
            ) from exc

        finally:
            connection.disconnect()

    def create_hotspot_user(
        self,
        *,
        username: str,
        password: str,
        profile: str,
        limit_uptime: int,
        comment: str | None = None,
    ):
        """
        Create a MikroTik HotSpot user.

        limit_uptime is provided in seconds and converted
        to RouterOS duration syntax.
        """

        connection = self._connect()

        try:
            api = connection.get_api()

            resource = api.get_resource(
                "/ip/hotspot/user"
            )

            # Prevent accidental duplicate creation.
            existing = resource.get(
                name=username
            )

            if existing:
                raise MikroTikError(
                    f"HotSpot user '{username}' already exists"
                )

            properties = {
                "name": username,
                "password": password,
                "profile": profile,
                "limit-uptime": self._seconds_to_routeros_time(
                    limit_uptime
                ),
            }

            if self.settings.mikrotik_hotspot_server:
                properties["server"] = (
                    self.settings.mikrotik_hotspot_server
                )

            if comment:
                properties["comment"] = comment

            result = resource.add(
                **properties
            )

            return result

        except MikroTikError:
            raise

        except Exception as exc:
            raise MikroTikError(
                f"Failed to create HotSpot user "
                f"'{username}': {exc}"
            ) from exc

        finally:
            connection.disconnect()

    @staticmethod
    def _seconds_to_routeros_time(seconds: int) -> str:
        """
        Convert seconds to RouterOS duration syntax.

        Examples:
            3600   -> 1h
            86400  -> 1d
            259200 -> 3d
        """

        if seconds <= 0:
            raise ValueError(
                "limit_uptime must be greater than zero"
            )

        if seconds % 86400 == 0:
            return f"{seconds // 86400}d"

        if seconds % 3600 == 0:
            return f"{seconds // 3600}h"

        if seconds % 60 == 0:
            return f"{seconds // 60}m"

        return f"{seconds}s"

    def test_connection(self) -> dict:
        """
        Test API connectivity and return router identity.
        """

        connection = self._connect()

        try:
            api = connection.get_api()

            identity = api.get_resource(
                "/system/identity"
            ).get()

            return {
                "connected": True,
                "identity": identity,
            }

        except Exception as exc:
            raise MikroTikError(
                f"MikroTik connection test failed: {exc}"
            ) from exc

        finally:
            connection.disconnect()