# pyopc

This module provides a Python interface to the Alphasense OPC-N2.

## Installation using pip

### Python 3
```
pip3 install git+https://github.com/waggle-sensor/pyopc
```

### Python 2
```
pip install git+https://github.com/waggle-sensor/pyopc
```

This will automatically fetch and install the module along with all of its
dependencies.

## Example Usage

```python
from alphasense import OPCN2
import time


with OPCN2('/dev/my-opc-device') as opc:
    opc.power_on()
    time.sleep(1)

    while True:
        # allows samples to collect for 10 seconds before reading.
        time.sleep(10)
        data = opc.get_histogram()
        print(data)
```
