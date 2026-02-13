import httpx
from fastapi import FastAPI, Request, Response

app = FastAPI()

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy(path: str, request: Request):
    # --- 1. Определение целевого URL ---
    destination_url = request.query_params.get("url")

    if not destination_url:
        if path.startswith("http"):
            destination_url = path
            # Восстанавливаем протокол, если FastAPI "съел" слеши
            if ":/" in destination_url and "://" not in destination_url:
                destination_url = destination_url.replace(":/", "://", 1)
        else:
            return Response("Error: Missing 'url' parameter. Usage: /?url=https://target.com", status_code=400)

    # --- 2. Подготовка параметров (удаляем 'url', оставляем остальные) ---
    request_params = dict(request.query_params)
    request_params.pop("url", None)

    # --- 3. Очистка заголовков ЗАПРОСА (Важная часть для анонимности) ---
    headers = dict(request.headers)
    
    # Список заголовков, которые нужно удалить, чтобы не раскрывать себя
    # и не ломать соединение
    headers_to_remove = [
        "host",             # Целевой сервер ждет свой хост
        "content-length",   # Httpx вычислит заново
        
        # Заголовки, раскрывающие реальный IP клиента (вас):
        "x-forwarded-for",  
        "x-real-ip", 
        "forwarded",
        "client-ip",
        "via",
        
        # Служебные заголовки соединения (hop-by-hop):
        "connection", 
        "upgrade", 
        "keep-alive"
    ]

    for key in headers_to_remove:
        # Удаляем без ошибок, если ключа нет (None)
        headers.pop(key, None)

    # Получаем тело запроса
    content = await request.body()

    async with httpx.AsyncClient(follow_redirects=False) as client:
        try:
            # --- 4. Выполнение запроса к целевому сайту ---
            response = await client.request(
                method=request.method,
                url=destination_url,
                headers=headers,
                params=request_params,
                content=content
            )
            
            # --- 5. Подготовка заголовков ОТВЕТА ---
            # Мы также должны почистить заголовки ответа от целевого сайта,
            # чтобы они не конфликтовали с FastAPI (например, сжатие gzip)
            response_headers = dict(response.headers)
            response_headers_to_remove = [
                "content-encoding", 
                "content-length", 
                "transfer-encoding", 
                "connection"
            ]
            
            for key in response_headers_to_remove:
                response_headers.pop(key, None)

            # --- 6. Возврат результата ---
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers
            )
            
        except Exception as e:
            return Response(f"Proxy error: {str(e)}", status_code=500)