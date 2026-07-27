"""Isolated edge-tts subprocess. Runs in its OWN process so its relaxed-TLS
workaround (needed only behind a TLS-intercepting egress proxy, e.g. this dev
sandbox) can never affect the bot's real upload TLS. In production with a clean
egress the relax is a no-op. Usage: python dd_tts.py <out.mp3> <voice> <rate> <text>
"""
import ssl, sys, asyncio
_o = ssl.create_default_context
def _r(*a, **k):
    c = _o(*a, **k); c.check_hostname = False; c.verify_mode = ssl.CERT_NONE; return c
ssl.create_default_context = _r
ssl._create_default_https_context = _r
import edge_tts

out, voice, rate, text = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
asyncio.run(edge_tts.Communicate(text, voice, rate=rate).save(out))
print("wrote", out)
