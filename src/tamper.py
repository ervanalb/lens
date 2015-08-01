import driver
import time

class TamperException(Exception): pass

t=driver.Tap()

threshold = 1000

print "Enabling MITM"
try:
    t.mitm()
    t.start_accel()
    accel_baseline = t.get_accel()

    while True:
        t.heartbeat(150)

        accel = t.get_accel()
        for base, reading in zip(accel_baseline, accel):
            if abs(base - reading) >= threshold:
                raise TamperException

        time.sleep(0.1)

except TamperException:
    print "Tamper!"
    t.heartbeat()
    t.passthru()

except KeyboardInterrupt:
    print "Got keyboard interrupt, shutting down gracefully..."
    t.heartbeat()
    t.passthru()

except:
    t.passthru()
    raise
