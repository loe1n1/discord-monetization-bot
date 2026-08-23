import aiohttp
import asyncio
from typing import Optional

class JokeGenerator:
    """Генератор случайных шуток через внешние API"""
    
    def __init__(self):
        self.joke_api_url = "https://official-joke-api.appspot.com/random_joke"
        self.dad_jokes_url = "https://icanhazdadjoke.com/slack"
    
    async def get_random_joke(self, joke_type: str = "official") -> Optional[dict]:
        """
        Получить случайную шутку из API
        
        Args:
            joke_type: "official" или "dad_jokes"
        
        Returns:
            dict с информацией о шутке или None при ошибке
        """
        url = self.joke_api_url if joke_type == "official" else self.dad_jokes_url
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if joke_type == "official":
                            return {
                                "setup": data.get("setup", ""),
                                "punchline": data.get("punchline", ""),
                                "type": data.get("type", "general"),
                                "id": data.get("id", 0)
                            }
                        else:  # dad_jokes
                            # Dad Jokes API возвращает массив в Slack формате
                            if "attachments" in data and len(data["attachments"]) > 0:
                                joke_text = data["attachments"][0].get("text", "")
                                return {
                                    "joke": joke_text,
                                    "type": "dad_joke"
                                }
        except asyncio.TimeoutError:
            print("⏱️ Timeout при получении шутки")
        except Exception as e:
            print(f"❌ Ошибка при получении шутки: {e}")
        
        return None
    
    async def get_formatted_joke(self, joke_type: str = "official") -> str:
        """
        Получить отформатированную шутку для Discord
        """
        joke = await self.get_random_joke(joke_type)
        
        if not joke:
            return "😅 Не удалось получить шутку, попробуйте позже..."
        
        if joke_type == "official":
            return f"**{joke['setup']}**\n\n||{joke['punchline']}||"
        else:
            return f"😂 {joke['joke']}"


# Пример использования
async def main():
    generator = JokeGenerator()
    
    print("=== Official Joke ===")
    joke1 = await generator.get_formatted_joke("official")
    print(joke1)
    
    print("\n=== Dad Joke ===")
    joke2 = await generator.get_formatted_joke("dad_jokes")
    print(joke2)


if __name__ == "__main__":
    asyncio.run(main())
