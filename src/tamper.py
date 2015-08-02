import driver
import time

t=driver.Tap()

threshold = 1000

print "Enabling MITM"
try:
    #t.mitm()
    t.start_accel()

    while True:
        accel_baseline = t.get_accel()

        tamper = False

        while not tamper:
            t.heartbeat(150)

            accel = t.get_accel()
            for base, reading in zip(accel_baseline, accel):
                if abs(base - reading) >= threshold:
                    print "Tamper!"
                    t.heartbeat()
                    for i in range(5):
                        time.sleep(0.01)
                        t.set_led(True)
                        time.sleep(0.01)
                        t.set_led(False)
                    tamper=True

            time.sleep(0.1)

except KeyboardInterrupt:
    print "Got keyboard interrupt, shutting down gracefully..."
    t.heartbeat()
    t.passthru()

except:
    t.passthru()
    raise
