import httpx

from app.config import settings


class HabitApiClient:
    """Small synchronous client for the FastAPI service."""

    def __init__(self) -> None:
        self.base_url = settings.api_base_url.rstrip("/")
        self.tokens: dict[int, str] = {}

    def _headers(self, telegram_id: int) -> dict[str, str]:
        token = self.tokens.get(telegram_id)
        return {"Authorization": f"Bearer {token}"} if token else {}

    def request(self, method: str, path: str, telegram_id: int | None = None, **kwargs):
        """Send a request to the API and raise readable API errors."""
        headers = kwargs.pop("headers", {})
        if telegram_id is not None:
            headers.update(self._headers(telegram_id))
        with httpx.Client(timeout=15) as client:
            response = client.request(
                method, f"{self.base_url}{path}", headers=headers, **kwargs
            )
        if response.is_error:
            try:
                detail = response.json().get("detail", "API request failed")
            except ValueError:
                detail = "API request failed"
            raise RuntimeError(f"{response.status_code}: {detail}")
        return response.json() if response.content else None

    def register(self, telegram_id: int, display_name: str, password: str) -> str:
        result = self.request("POST", "/auth/register", json={
            "telegram_id": telegram_id,
            "display_name": display_name or "Telegram user",
            "password": password,
        })
        self.tokens[telegram_id] = result["access_token"]
        return result["access_token"]

    def login(self, telegram_id: int, password: str) -> str:
        result = self.request("POST", "/auth/token", json={
            "telegram_id": telegram_id,
            "password": password,
        })
        self.tokens[telegram_id] = result["access_token"]
        return result["access_token"]

    def list_habits(self, telegram_id: int):
        return self.request("GET", "/habits", telegram_id)

    def create_habit(self, telegram_id: int, data: dict):
        return self.request("POST", "/habits", telegram_id, json=data)

    def update_habit(self, telegram_id: int, habit_id: int, data: dict):
        return self.request("PATCH", f"/habits/{habit_id}", telegram_id, json=data)

    def delete_habit(self, telegram_id: int, habit_id: int):
        return self.request("DELETE", f"/habits/{habit_id}", telegram_id)

    def complete_habit(self, telegram_id: int, habit_id: int, completed: bool):
        return self.request(
            "POST", f"/habits/{habit_id}/completion", telegram_id,
            json={"is_completed": completed},
        )

    def get_stats(self, telegram_id: int, habit_id: int):
        return self.request("GET", f"/habits/{habit_id}/stats", telegram_id)
