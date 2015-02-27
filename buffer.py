from cStringIO import StringIO

# http://stackoverflow.com/questions/10917581/efficient-fifo-queue-for-arbitrarily-sized-chunks-of-bytes-in-python

class FifoBuffer(object):
    def __init__(self):
        self.buf = StringIO()

    def read(self, *args, **kwargs):
        """Reads data from buffer"""
        self.buf.read(*args, **kwargs)

    def write(self, *args, **kwargs):
        """Appends data to buffer"""
        current_read_fp = self.buf.tell()
        if current_read_fp > 10 * 1024 * 1024:
            # Buffer is holding 10MB of used data, time to compact
            new_buf = StringIO()
            new_buf.write(self.buf.read())
            self.buf = new_buf
            current_read_fp = 0

        self.buf.seek(0, 2)    # Seek to end
        self.buf.write(*args, **kwargs)

        self.buf.seek(current_read_fp)
