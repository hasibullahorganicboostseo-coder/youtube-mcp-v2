import os
import asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from googleapiclient.discovery import build

app = FastAPI(title="YouTube MCP Server")
mcp = Server("youtube-mcp")
sse_transport = None

@mcp.tool()
async def search_youtube(query: str, max_results: int = 5) -> str:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return "Error: YOUTUBE_API_KEY environment variable is not set."
    
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        response = youtube.search().list(
            q=query, part="snippet", maxResults=max_results, type="video"
        ).execute()
        
        results = []
        for item in response.get("items", []):
            title = item["snippet"]["title"]
            channel = item["snippet"]["channelTitle"]
            video_id = item["id"]["videoId"]
            results.append(f"Title: {title}\nChannel: {channel}\nURL: https://youtube.com/watch?v={video_id}")
            
        return "\n\n".join(results) if results else "No results found."
    except Exception as e:
        return f"API Error: {str(e)}"

@mcp.tool()
async def get_video_seo_metadata(video_id: str) -> str:
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        return "Error: YOUTUBE_API_KEY environment variable is not set."
    
    try:
        youtube = build("youtube", "v3", developerKey=api_key)
        response = youtube.videos().list(part="snippet,statistics", id=video_id).execute()
        
        if not response.get("items"):
            return "Video not found."
            
        snippet = response["items"][0]["snippet"]
        stats = response["items"][0]["statistics"]
        tags = ", ".join(snippet.get("tags", ["No tags found"]))
        
        return f"Title: {snippet['title']}\nTags: {tags}\nViews: {stats.get('viewCount')}\nDescription:\n{snippet['description'][:400]}..."
    except Exception as e:
        return f"API Error: {str(e)}"

@app.get("/sse")
async def sse_endpoint(request: Request):
    global sse_transport
    sse_transport = SseServerTransport("/messages")
    
    async def connect_mcp():
        await mcp.connect(sse_transport)
        
    asyncio.create_task(connect_mcp())
    return StreamingResponse(sse_transport.generator, media_type="text/event-stream")

@app.post("/messages")
async def messages_endpoint(request: Request):
    global sse_transport
    if not sse_transport:
        return {"error": "SSE not initialized"}
    message = await request.json()
    await sse_transport.handle_post_message(message)
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)