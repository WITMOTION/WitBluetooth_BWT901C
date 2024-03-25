# coding:UTF-8
import threading
import time
import struct
import bleak
import asyncio


# 设备实例 Device instance
class DeviceModel:
    # region 属性 attribute
    # 设备名称 deviceName
    deviceName = "我的设备"

    # 设备数据字典 Device Data Dictionary
    deviceData = {}

    # 设备是否开启
    isOpen = False

    # 临时数组 Temporary array
    TempBytes = []

    # endregion

    def __init__(self, deviceName, mac, callback_method):
        print("Initialize device model")
        # 设备名称（自定义） Device Name
        self.deviceName = deviceName
        self.mac = mac
        self.client = None
        self.writer_characteristic = None
        self.isOpen = False
        self.callback_method = callback_method
        self.deviceData = {}

    # region 获取设备数据 Obtain device data
    # 设置设备数据 Set device data
    def set(self, key, value):
        # 将设备数据存到键值 Saving device data to key values
        self.deviceData[key] = value

    # 获得设备数据 Obtain device data
    def get(self, key):
        # 从键值中获取数据，没有则返回None Obtaining data from key values
        if key in self.deviceData:
            return self.deviceData[key]
        else:
            return None

    # 删除设备数据 Delete device data
    def remove(self, key):
        # 删除设备键值
        del self.deviceData[key]

    # endregion

    # 打开设备 open Device
    async def openDevice(self):
        print("Opening device......")
        # 获取设备的服务和特征 Obtain the services and characteristic of the device
        async with bleak.BleakClient(self.mac) as client:
            self.client = client
            self.isOpen = True
            # 设备UUID常量 Device UUID constant
            target_service_uuid = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
            target_characteristic_uuid_read = "49535343-1e4d-4bd9-ba61-23c647249616"
            target_characteristic_uuid_write = "49535343-8841-43f4-a8d4-ecbe34729bb3"
            notify_characteristic = None

            print("Matching services......")
            # 匹配服务和特征值 Matching services and characteristic values
            for service in client.services:
                if service.uuid == target_service_uuid:
                    print(f"Service: {service}")
                    print("Matching characteristic......")
                    for characteristic in service.characteristics:
                        if characteristic.uuid == target_characteristic_uuid_read:
                            notify_characteristic = characteristic
                        if characteristic.uuid == target_characteristic_uuid_write:
                            self.writer_characteristic = characteristic
                    if notify_characteristic:
                        break

            if self.writer_characteristic:
                pass

            if notify_characteristic:
                print(f"Characteristic: {notify_characteristic}")
                # 设置通知以接收数据 Set up notifications to receive data
                await client.start_notify(notify_characteristic.uuid, self.onDataReceived)

                # 保持连接打开 Keep connected and open
                try:
                    while self.isOpen:
                        await asyncio.sleep(1)
                except asyncio.CancelledError:
                    pass
                finally:
                    # 在退出时停止通知 Stop notification on exit
                    await client.stop_notify(notify_characteristic.uuid)
            else:
                print("No matching services or characteristic found")

    # 关闭设备  close Device
    def closeDevice(self):
        self.isOpen = False
        print("The device is turned off")

    # region 数据解析 data analysis
    # 串口数据处理  Serial port data processing
    def onDataReceived(self, sender, data):
        tempdata = bytes.fromhex(data.hex())
        for var in tempdata:
            self.TempBytes.append(var)
            # 必须是0x55开头 Must start with 0x55
            if self.TempBytes[0] != 0x55:
                del self.TempBytes[0]
                continue
            if len(self.TempBytes) == 11:
                # 检验和判断 Checksum
                if (sum(self.TempBytes[:10]) & 0xff) == self.TempBytes[10]:
                    self.processData(self.TempBytes)
                    self.TempBytes.clear()
                else:
                    del self.TempBytes[0]
                    continue

    # 数据解析 data analysis
    def processData(self, Bytes):
        # 时间 Time
        if Bytes[1] == 0x50:
            year = Bytes[2] + 2000
            mon = Bytes[3]
            day = Bytes[4]
            hour = Bytes[5]
            minute = Bytes[6]
            sec = Bytes[7]
            mils = Bytes[9] << 8 | Bytes[8]
            self.set("time", "{}-{}-{} {}:{}:{}:{}".format(year, mon, day, hour, minute, sec, mils))
        # 加速度 Acceleration
        elif Bytes[1] == 0x51:
            Ax = self.getSignInt16(Bytes[3] << 8 | Bytes[2]) / 32768 * 16
            Ay = self.getSignInt16(Bytes[5] << 8 | Bytes[4]) / 32768 * 16
            Az = self.getSignInt16(Bytes[7] << 8 | Bytes[6]) / 32768 * 16
            self.set("AccX", round(Ax, 3))
            self.set("AccY", round(Ay, 3))
            self.set("AccZ", round(Az, 3))
            self.callback_method(self)
        # 角速度 Angular velocity
        elif Bytes[1] == 0x52:
            Gx = self.getSignInt16(Bytes[3] << 8 | Bytes[2]) / 32768 * 2000
            Gy = self.getSignInt16(Bytes[5] << 8 | Bytes[4]) / 32768 * 2000
            Gz = self.getSignInt16(Bytes[7] << 8 | Bytes[6]) / 32768 * 2000
            self.set("AsX", round(Gx, 3))
            self.set("AsY", round(Gy, 3))
            self.set("AsZ", round(Gz, 3))
        # 角度 Angle
        elif Bytes[1] == 0x53:
            AngX = self.getSignInt16(Bytes[3] << 8 | Bytes[2]) / 32768 * 180
            AngY = self.getSignInt16(Bytes[5] << 8 | Bytes[4]) / 32768 * 180
            AngZ = self.getSignInt16(Bytes[7] << 8 | Bytes[6]) / 32768 * 180
            self.set("AngleX", round(AngX, 2))
            self.set("AngleY", round(AngY, 2))
            self.set("AngleZ", round(AngZ, 2))
        # 磁场 Magnetic field
        elif Bytes[1] == 0x54:
            Hx = self.getSignInt16(Bytes[3] << 8 | Bytes[2]) / 120
            Hy = self.getSignInt16(Bytes[5] << 8 | Bytes[4]) / 120
            Hz = self.getSignInt16(Bytes[7] << 8 | Bytes[6]) / 120
            self.set("HX", round(Hx, 3))
            self.set("HY", round(Hy, 3))
            self.set("HZ", round(Hz, 3))
        else:
            pass

    # 获得int16有符号数 Obtain int16 signed number
    @staticmethod
    def getSignInt16(num):
        if num >= pow(2, 15):
            num -= pow(2, 16)
        return num

    # endregion

    # 发送串口数据 Sending serial port data
    async def sendData(self, data):
        try:
            if self.client.is_connected and self.writer_characteristic is not None:
                await self.client.write_gatt_char(self.writer_characteristic.uuid, bytes(data))
        except Exception as ex:
            print(ex)

    # 读取寄存器 read register
    async def readReg(self, regAddr):
        # 封装读取指令并向串口发送数据 Encapsulate read instructions and send data to the serial port
        await self.sendData(self.get_readBytes(regAddr))

    # 写入寄存器 Write Register
    async def writeReg(self, regAddr, sValue):
        # 解锁 unlock
        self.unlock()
        # 延迟100ms Delay 100ms
        time.sleep(0.1)
        # 封装写入指令并向串口发送数据
        await self.sendData(self.get_writeBytes(regAddr, sValue))
        # 延迟100ms Delay 100ms
        time.sleep(0.1)
        # 保存 save
        self.save()

    # 读取指令封装 Read instruction encapsulation
    @staticmethod
    def get_readBytes(regAddr):
        # 初始化
        tempBytes = [None] * 5
        tempBytes[0] = 0xff
        tempBytes[1] = 0xaa
        tempBytes[2] = 0x27
        tempBytes[3] = regAddr
        tempBytes[4] = 0
        return tempBytes

    # 写入指令封装 Write instruction encapsulation
    @staticmethod
    def get_writeBytes(regAddr, rValue):
        # 初始化
        tempBytes = [None] * 5
        tempBytes[0] = 0xff
        tempBytes[1] = 0xaa
        tempBytes[2] = regAddr
        tempBytes[3] = rValue & 0xff
        tempBytes[4] = rValue >> 8
        return tempBytes

    # 解锁
    def unlock(self):
        cmd = self.get_writeBytes(0x69, 0xb588)
        self.sendData(cmd)

    # 保存
    def save(self):
        cmd = self.get_writeBytes(0x00, 0x0000)
        self.sendData(cmd)
