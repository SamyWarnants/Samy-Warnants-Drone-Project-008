from pymavlink import mavutil
import time

SERIAL_PORT = '/dev/ttyTHS1'
BAUD_RATE = 57600

class DroneController:
    """A comprehensive class to control a drone via MAVLink."""
    def __init__(self, port, baud):
        print(f"Connecting to Pixhawk on {port} at {baud} baud...")
        self.master = mavutil.mavlink_connection(port, baud=baud)
        self.wait_for_heartbeat()

    def wait_for_heartbeat(self):
        print("Waiting for heartbeat...")
        self.master.wait_heartbeat()
        print(f"Heartbeat from system (system {self.master.target_system} component {self.master.target_component})")

    def set_mode(self, mode):
        print(f"Setting mode to {mode}...")
        # Check if mode is available
        if mode not in self.master.mode_mapping():
            print(f"Unknown mode : {mode}")
            print(f"Available modes:", list(self.master.mode_mapping().keys()))
            return
        
        mode_id = self.master.mode_mapping()[mode]
        self.master.set_mode(mode_id)
        
        # Wait for ACK
        ack = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=3)
        print(f"Set Mode ACK: {ack}")

    def arm(self):
        print("Arming motors...")
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
            1, 21196, 0, 0, 0, 0, 0
        )
        self.master.motors_armed_wait()
        print("Armed!")

    def disarm(self):
        print("Disarming motors...")
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0,
            0, 21196, 0, 0, 0, 0, 0
        )
        self.master.motors_disarmed_wait()
        print("Disarmed!")

    def takeoff(self, altitude):
        print(f"Taking off to {altitude}m...")
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0,
            0, 0, 0, 0, 0, 0, altitude
        )
        ack = self.master.recv_match(type='COMMAND_ACK', blocking=True, timeout=3)
        print(f"Takeoff ACK: {ack}")

    def set_velocity_body(self, vx, vy, vz, yaw_rate=0.0):
        # Sends velocity commands in GUIDED mode (m/s and rad/s)
        self.master.mav.set_position_target_local_ned_send(
            0, self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_NED,
            int(0b011111000111), # type_mask (only speeds enabled)
            0, 0, 0, # x, y, z positions (not used)
            vx, vy, vz, # x, y, z velocity in m/s
            0, 0, 0, # x, y, z acceleration (not used)
            0, yaw_rate # yaw, yaw_rate
        )

    def send_rc_override(self, channels):
        # channels is a list of 8 PWM values (1000-2000), 0 means release
        # e.g., rc = [1500, 1500, 1500, 1500, 0, 0, 0, 0] # Roll, Pitch, Throttle, Yaw
        self.master.mav.rc_channels_override_send(
            self.master.target_system, self.master.target_component,
            *channels
        )

    def request_message_interval(self, message_id, frequency_hz):
        self.master.mav.command_long_send(
            self.master.target_system, self.master.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            message_id,
            1e6 / frequency_hz,
            0, 0, 0, 0, 0
        )

if __name__ == "__main__":
    drone = DroneController(SERIAL_PORT, BAUD_RATE)
    
    print("Listening... Waiting for the drone to be ARMED and in ALT_HOLD mode.")
    print("You can arm via RC or Ground Control Station.")
    
    # Request RAW_IMU (message ID 27) at 10Hz to ensure we get gyro data
    drone.request_message_interval(mavutil.mavlink.MAVLINK_MSG_ID_RAW_IMU, 10)
    
    try:
        while True:
            # We must process ALL pending messages to keep internal flightmode and armed states perfectly up-to-date
            msg = drone.master.recv_match(blocking=True, timeout=0.05)
            while msg:
                # Exclude BAD_DATA to avoid cluttering if you only want valid mavlink messages
                if msg.get_type() != 'BAD_DATA':
                    pass # print(msg) - You can uncomment this to print everything, but it will be very fast!
                    if msg.get_type() == 'RAW_IMU':
                        print(f"Gyro Data: X:{msg.xgyro} Y:{msg.ygyro} Z:{msg.zgyro}")
                    elif msg.get_type() == 'HEARTBEAT':
                        print(f"Heartbeat - Mode: {drone.master.flightmode}, Armed: {drone.master.motors_armed()}")
                        
                msg = drone.master.recv_match(blocking=False)
            
            is_armed = drone.master.motors_armed()
            current_mode = drone.master.flightmode
            
            if is_armed and current_mode == "ALT_HOLD":
                print("==> Detected ARMED + ALT_HOLD context! Initiating motor spin sequence...")
                
                # Spin up throttle from 1000 to 2000
                for pwm in range(1000, 2001, 50):
                    # Periodically check if the user disarmed or switched modes mid-sequence
                    msg = drone.master.recv_match(blocking=False)
                    while msg:
                        if msg.get_type() != 'BAD_DATA':
                            if msg.get_type() == 'RAW_IMU':
                                print(f"Gyro Data: X:{msg.xgyro} Y:{msg.ygyro} Z:{msg.zgyro}")
                            elif msg.get_type() == 'HEARTBEAT':
                                print(f"Heartbeat - Mode: {drone.master.flightmode}, Armed: {drone.master.motors_armed()}")
                        msg = drone.master.recv_match(blocking=False)
                        
                    if not drone.master.motors_armed() or drone.master.flightmode != "ALT_HOLD":
                        print("State changed mid-spin. Aborting sequence.")
                        break
                    
                    drone.send_rc_override([1500, 1500, pwm, 1500, 0, 0, 0, 0])
                    time.sleep(0.1)
                    
                # Spin down throttle from 2000 to 1000
                for pwm in range(2000, 999, -50):
                    msg = drone.master.recv_match(blocking=False)
                    while msg:
                        if msg.get_type() != 'BAD_DATA':
                            if msg.get_type() == 'RAW_IMU':
                                print(f"Gyro Data: X:{msg.xgyro} Y:{msg.ygyro} Z:{msg.zgyro}")
                            elif msg.get_type() == 'HEARTBEAT':
                                print(f"Heartbeat - Mode: {drone.master.flightmode}, Armed: {drone.master.motors_armed()}")
                        msg = drone.master.recv_match(blocking=False)
                        
                    if not drone.master.motors_armed() or drone.master.flightmode != "ALT_HOLD":
                        print("State changed mid-spin. Aborting sequence.")
                        break
                        
                    drone.send_rc_override([1500, 1500, pwm, 1500, 0, 0, 0, 0])
                    time.sleep(0.1)
                    
            else:
                # Neutralize overrides if we are not in the active test state
                drone.send_rc_override([0, 0, 0, 0, 0, 0, 0, 0])
                
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting...")
    finally:
        print("Releasing RC Override and returning control...")
        drone.send_rc_override([0, 0, 0, 0, 0, 0, 0, 0])

