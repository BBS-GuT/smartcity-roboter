class Image: pass
class CompressedImage:
    def __init__(self, **k): self.__dict__.update(k)
class LaserScan: pass
class Imu: pass
