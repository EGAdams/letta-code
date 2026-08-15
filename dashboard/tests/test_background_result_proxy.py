import threading

from background_result_proxy import BackgroundResultProxy


def test_proxy_returns_immediately_and_shares_background_refresh():
    release = threading.Event()
    calls = []

    def load(value):
        calls.append(value)
        release.wait(1)
        return value

    proxy = BackgroundResultProxy(loader=load, name='test-refresh')

    assert proxy.get('one', 'loaded', default='pending') == 'pending'
    assert proxy.get('one', 'loaded', default='pending') == 'pending'
    assert calls == ['loaded']
    release.set()
    proxy._entries['one']['future'].result(timeout=1)
    assert proxy.get('one', 'loaded', default='pending') == 'loaded'
