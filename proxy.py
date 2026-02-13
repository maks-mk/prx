import httpx
from fastapi import FastAPI, Request, Response

app = FastAPI()

# Мы убрали TARGET_URL, так как теперь адрес будет приходить в запросе

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request):
    # 1. Получаем целевой URL из параметров запроса (?url=https://...)
    # Если параметра нет, пробуем взять его из пути (на случай вызова /https://site.com)
    destination_url = request.query_params.get("url")

    if not destination_url:
        # Попытка прочитать URL из пути, если он передан как /https://google.com
        if path.startswith("http"):
            destination_url = path
            # FastAPI/Starlette могут "съедать" двойные слеши, восстанавливаем их
            if ":/" in destination_url and "://" not in destination_url:
                destination_url = destination_url.replace(":/", "://", 1)
        else:
            return Response("Error: Missing 'url' parameter. Usage: /?url=https://target.com", status_code=400)

    # 2. Подготавливаем параметры для отправки (удаляем наш служебный параметр 'url')
    request_params = dict(request.query_params)
    request_params.pop("url", None)

    async with httpx.AsyncClient(follow_redirects=False) as client:
        # 3. Копируем заголовки
        headers = dict(request.headers)
        headers.pop("host", None) # Удаляем Host, чтобы не смущать целевой сервер
        headers.pop("content-length", None) # Httpx сам пересчитает длину

        # Получаем тело запроса
        content = await request.body()

        try:
            # 4. Делаем запрос к целевому сервису
            response = await client.request(
                method=request.method,
                url=destination_url,
                headers=headers,
                params=request_params, # Передаем оставшиеся параметры
                content=content
            )
            
            # 5. Возвращаем ответ как есть
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
        except Exception as e:
            return Response(f"Proxy error: {str(e)}", status_code=500)