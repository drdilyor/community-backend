from typing import Optional, Any

import aiohttp
from fastapi import FastAPI, Body, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class User(BaseModel):
    email: str
    password: str


class SessionsResult(BaseModel):
    token: str
    user: Any


app = FastAPI()
base_url = 'https://community.uzbekcoders.uz/api/v1'
noop_jar = aiohttp.DummyCookieJar()
client = aiohttp.ClientSession(cookie_jar=noop_jar)
origins = '*'
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def decode_token(token):
    session_id, _, remember_me = token.partition(';')
    if not remember_me or not session_id:
        raise HTTPException(status_code=400, detail='Invalid token')
    return {'sessionId': session_id, 'remember_me': remember_me}


@app.post('/sessions', response_model=SessionsResult)
async def create_session(user: User):
    # obtain csrf token
    res = await client.get(base_url)
    session_id = res.cookies['sessionId'].value
    res = await client.post(f'{base_url}/sessions', json=user.dict(), cookies=res.cookies)
    data = await res.json()
    if res.status == 200:
        return {
            'token': f'{session_id};{res.cookies["remember_me"].value}',
            'user': data,
        }
    else:
        raise HTTPException(status_code=res.status, detail=data)


def validate_url(url: str):
    url = url.removeprefix('/')
    if url.startswith('.'):
        raise HTTPException(400, detail='Url cannot start with a dot')
    return url

async def handle_response(res):
    if res.status == 200:
        data = await res.json()
        return data
    else:
        if res.headers['Content-Type'] and res.headers['Content-Type'].startswith('application/json'):
            return JSONResponse(status_code=res.status, content=await res.json())
        else:
            print(res.headers['Content-Type'])
            print(await res.read())
            return JSONResponse(status_code=res.status)

async def do_request(method, url, token, json=None):
    print(json)
    cookies = decode_token(token) if token else {}
    headers = {}
    if method != 'get':
        # obtain csrf
        res = await client.get(base_url, cookies=cookies)
        for i in res.cookies:
            cookies[i] = res.cookies[i].value
        headers = {'csrf-token': cookies['CSRF-Token']}

    print('; '.join(k + '=' + v for k, v in cookies.items()))
    res = await getattr(client, method)(
        f'{base_url}/{url}',
        cookies=cookies,
        headers=headers,
        json=json or {},
    )
    return res


# Note(myself): OpenAPI doesn't support a way to declare a path parameter to
# contain a path inside, as that could lead to scenarios that are difficult to
# test and define.

@app.get('/{url:path}')
async def api_get(request: Request, url: str, x_token: str = Header(None)):
    url = validate_url(url)
    if request.query_params:
        url += '?' + str(request.query_params)
    return await handle_response(await do_request('get', url, x_token))

@app.post('/{url:path}')
async def api_post(request: Request, url: str, body: Optional[Any] = Body(None), x_token: str = Header(...)):
    url = validate_url(url)
    if request.query_params:
        url += '?' + str(request.query_params)
    return await handle_response(await do_request('post', url, x_token, body))

@app.put('/{url:path}')
async def api_put(request: Request, url: str, x_token: str = Header(...)):
    url = validate_url(url)
    if request.query_params:
        url += '?' + str(request.query_params)
    return await handle_response(await do_request('put', url, x_token, body))

@app.delete('/{url:path}')
async def api_delete(request: Request, url: str, body: Optional[Any] = Body(None), x_token: str = Header(...)):
    url = validate_url(url)
    if request.query_params:
        url += '?' + str(request.query_params)
    return await handle_response(await do_request('delete', url, x_token, body))
