import unittest
from src.core.retry import retry_with_backoff

class TestRetry(unittest.TestCase):

    def test_immediate_success(self):
        calls = 0
        def op():
            nonlocal calls
            calls += 1
            return "ok"

        res = retry_with_backoff(op, max_retries=3, initial_delay=0.01)
        self.assertEqual(res, "ok")
        self.assertEqual(calls, 1)

    def test_success_on_retry(self):
        calls = 0
        def op():
            nonlocal calls
            calls += 1
            if calls < 2:
                raise ConnectionResetError("Erro transitório de rede simulado")
            return "recovered"

        res = retry_with_backoff(op, max_retries=3, initial_delay=0.01, jitter=False)
        self.assertEqual(res, "recovered")
        self.assertEqual(calls, 2)

    def test_exhausted_retries_raises_exception(self):
        calls = 0
        def op():
            nonlocal calls
            calls += 1
            raise TimeoutError("Timeout persistente de API")

        with self.assertRaises(TimeoutError):
            retry_with_backoff(op, max_retries=2, initial_delay=0.01, jitter=False)
        self.assertEqual(calls, 2)

if __name__ == "__main__":
    unittest.main()
