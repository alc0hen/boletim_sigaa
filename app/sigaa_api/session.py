import aiohttp
import asyncio
from .types import HTTPMethod
from .page import SigaaPage
from .exceptions import SigaaConnectionError
from urllib.parse import urljoin, urlparse

class SigaaSession:
    def __init__(self, url, cookies=None):
        self.base_url = url
        self._session = None
        self.headers = {
            'User-Agent': 'SIGAA-Api/1.0 (https://github.com/GeovaneSchmitz/sigaa-api)',
            'Accept-Encoding': 'br, gzip, deflate',
            'Accept': '*/*',
            'Cache-Control': 'max-age=0',
            'DNT': '1'
        }
        self._initial_cookies = cookies

    async def _get_session(self):
        if self._session is None:
            cookie_jar = aiohttp.CookieJar(unsafe=True)
            if self._initial_cookies:
                cookie_jar.update_cookies(self._initial_cookies)
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                cookie_jar=cookie_jar
            )
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def request(self, method, path, data=None, json=None, retry_count=0, redirect_count=0, **kwargs):
        session = await self._get_session()

        # Enforce manual redirect handling for security check
        kwargs['allow_redirects'] = False

        if path.startswith('http'):
            url = path
        else:
            url = urljoin(self.base_url, path)

        base_netloc = urlparse(self.base_url).netloc
        req_netloc = urlparse(url).netloc

        if req_netloc != base_netloc:
            raise ValueError(f"Security Alert: Potential SSRF attempt blocked. Request to {req_netloc} not allowed.")

        try:
            async with session.request(method, url, data=data, json=json, **kwargs) as response:
                # Handle Redirects Manually
                if response.status in (301, 302, 303, 307, 308):
                    if redirect_count >= 10:
                        raise SigaaConnectionError("Too many redirects")

                    location = response.headers.get('Location')
                    if not location:
                        # Should not happen for 3xx, but if so, treat as normal response
                        pass
                    else:
                        new_url = urljoin(str(response.url), location)

                        # Validate Redirect Target Domain
                        new_netloc = urlparse(new_url).netloc
                        if new_netloc != base_netloc:
                             raise ValueError(f"Security Alert: External redirect blocked. Redirect to {new_netloc} not allowed.")

                        # Determine method for next request
                        # 301/302/303 -> GET usually
                        # 307/308 -> Preserve method
                        next_method = method
                        if response.status in (301, 302, 303):
                            next_method = HTTPMethod.GET.value
                            # Clear data/json for GET
                            data = None
                            json = None

                        return await self.request(
                            next_method,
                            new_url,
                            data=data,
                            json=json,
                            retry_count=retry_count,
                            redirect_count=redirect_count + 1,
                            **kwargs
                        )

                # Process Final Response
                final_netloc = urlparse(str(response.url)).netloc
                if final_netloc != base_netloc:
                    raise ValueError(f"Security Alert: External redirect blocked. Redirect to {final_netloc} not allowed.")

                body = await response.text()
                page = SigaaPage(
                    url=response.url,
                    body=body,
                    headers=dict(response.headers),
                    method=method,
                    status_code=response.status,
                    request_headers=dict(response.request_info.headers)
                )

                if page.soup.find(id='btnNaoResponderContinuarSigaa'):
                    if retry_count >= 3:
                        return page
                    await self._handle_questionnaire(page)
                    # Retry the ORIGINAL request (resetting redirect count)
                    return await self.request(method, path, data=data, json=json, retry_count=retry_count+1, **kwargs)

                return page

        except aiohttp.ClientError as e:
            raise SigaaConnectionError(f"Connection error: {e}")

    async def _handle_questionnaire(self, page):
        """
        Submits the form to skip the questionnaire.
        """
        skip_button = page.soup.find(id='btnNaoResponderContinuarSigaa')
        if not skip_button:
            return
        form = skip_button.find_parent('form')
        if not form:
            return
        action = form.get('action')
        form_id = form.get('id')
        if not action or not form_id:
            return

        action_url = urljoin(str(page.url), action)
        base_netloc = urlparse(self.base_url).netloc
        action_netloc = urlparse(action_url).netloc

        if action_netloc != base_netloc:
            return

        view_state = page.view_state
        post_values = {
            form_id: form_id,
            'btnNaoResponderContinuarSigaa': 'btnNaoResponderContinuarSigaa'
        }

        if view_state:
            post_values['javax.faces.ViewState'] = view_state

        session = await self._get_session()
        async with session.post(action_url, data=post_values, allow_redirects=False) as resp:
             await resp.text()

    async def get(self, path, **kwargs):
        return await self.request(HTTPMethod.GET.value, path, **kwargs)

    async def post(self, path, data=None, **kwargs):
        return await self.request(HTTPMethod.POST.value, path, data=data, **kwargs)

    async def follow_all_redirects(self, page):
        """
        Follow redirects manually if needed, although aiohttp handles them by default.
        However, if Sigaa returns 302 with a body that acts as a page (JS redirect) or meta refresh,
        we might need logic here.
        But standard 302 are handled by aiohttp allow_redirects=True (default).
        The TS code had explicit follow logic, likely because it wanted to inspect intermediate pages
        or control the flow strictly.
        """
        return page
