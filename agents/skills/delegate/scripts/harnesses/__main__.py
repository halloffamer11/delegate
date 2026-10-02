"""`python3 scripts/harnesses relays` prints one relay directory per line, for
ads.sh, which cannot import Python."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import harnesses  # noqa: E402

if sys.argv[1:] == ["relays"]:
    for h in harnesses.REGISTRY:
        print(h.relay)
elif sys.argv[1:] == ["names"]:
    for h in harnesses.REGISTRY:
        print(h.name)
else:
    sys.exit("usage: python3 harnesses relays|names")
