import Jetson.GPIO as GPIO
import time

# Pin 32 refers to BOARD pin 32, which is physically on the Jetson Orin Nano header.
# Often mapped to PWM0 or PWM1 depending on the exact carrier board
SERVO_PIN = 32

def main():
    # Setup Jetson.GPIO
    GPIO.setwarnings(False)
    # Using BOARD numbering mode to refer to the physical pin 32 on the 40-pin header
    GPIO.setmode(GPIO.BOARD) 
    
    # Configure the pin as an output
    GPIO.setup(SERVO_PIN, GPIO.OUT)

    # Initialize hardware PWM on pin 32 to 50Hz (Standard for standard hobby servos)
    pwm = GPIO.PWM(SERVO_PIN, 50)
    
    # Start the cycle at 0 (servo is off)
    pwm.start(0)

    print("Starting servo loop on pin 32. Press Ctrl+C to stop.")

    try:
        while True:
            # Move forward (approx 180 degrees)
            # 12.5% duty cycle is roughly 2.5ms pulse width
            pwm.ChangeDutyCycle(12.5)
            print("Moving Forward...")
            time.sleep(1)
            
            # Move backward (approx 0 degrees)
            # 2.5% duty cycle is roughly 0.5ms pulse width
            pwm.ChangeDutyCycle(2.5)
            print("Moving Backward...")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nKeyboard interrupt detected. Stopping...")
        
    finally:
        # Clean up resources safely
        pwm.stop()
        GPIO.cleanup()
        print("GPIO cleaned up. Exiting.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Jetson GPIO Super Variant Test Script
Tests GPIO library functionality on Jetson Orin Nano Super variants
"""

import os
import sys

def test_device_detection():
    """Test device detection and hardware info"""
    print("🔍 JETSON GPIO SUPER VARIANT TEST")
    print("=" * 50)

    # Check device tree information
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().strip()
        print(f"📋 Device Model: {model}")

        with open('/proc/device-tree/compatible', 'r') as f:
            compatible = f.read().replace('\x00', ' ').strip()
        print(f"🔧 Compatible: {compatible}")

        # Check if this is a Super variant
        is_super = '-super' in compatible
        print(f"🎯 Super Variant: {'✅ YES' if is_super else '❌ NO'}")

        return is_super

    except Exception as e:
        print(f"❌ Device detection failed: {e}")
        return False

def test_gpio_import():
    """Test GPIO library import"""
    print(f"\n🧪 Testing GPIO Library Import...")

    try:
        import Jetson.GPIO as GPIO
        print("✅ Jetson.GPIO imported successfully!")

        # Test basic constants
        print(f"📌 GPIO Mode Constants:")
        print(f"   BOARD: {GPIO.BOARD}")
        print(f"   BCM: {GPIO.BCM}")

        # Test Tegra-specific constants if available
        try:
            print(f"   TEGRA_SOC: {GPIO.TEGRA_SOC}")
            print(f"   CVM: {GPIO.CVM}")
            print("✅ Tegra modes available")
        except AttributeError:
            print("⚠️  Tegra modes not available (older GPIO library)")

        return True

    except Exception as e:
        print(f"❌ GPIO import failed: {e}")
        return False

def test_gpio_functionality():
    """Test basic GPIO functionality"""
    print(f"\n⚡ Testing GPIO Functionality...")

    try:
        import Jetson.GPIO as GPIO

        # Test mode setting
        GPIO.setmode(GPIO.BOARD)
        print("✅ GPIO mode set to BOARD")

        # Test pin setup (pin 7 as output - safe test pin)
        test_pin = 7
        GPIO.setup(test_pin, GPIO.OUT)
        print(f"✅ Pin {test_pin} configured as output")

        # Test pin output
        GPIO.output(test_pin, GPIO.HIGH)
        state = GPIO.input(test_pin)
        print(f"✅ Pin {test_pin} output test: {state}")

        # Clean up
        GPIO.cleanup()
        print("✅ GPIO cleanup successful")

        return True

    except Exception as e:
        print(f"❌ GPIO functionality test failed: {e}")
        return False

def main():
    """Run complete GPIO Super variant test"""

    print("🏗️  JETSON ORIN NANO SUPER GPIO COMPATIBILITY TEST")
    print("=" * 60)
    print("This script verifies GPIO library compatibility with Super variants")
    print()

    # Step 1: Device Detection
    is_super = test_device_detection()

    # Step 2: GPIO Import
    import_success = test_gpio_import()

    # Step 3: GPIO Functionality
    functionality_success = False
    if import_success:
        functionality_success = test_gpio_functionality()

    # Results Summary
    print(f"\n🏆 TEST RESULTS SUMMARY")
    print("=" * 30)
    print(f"Device Detection: {'✅ PASS' if is_super else '⚠️  Not Super variant'}")
    print(f"GPIO Import: {'✅ PASS' if import_success else '❌ FAIL'}")
    print(f"GPIO Functionality: {'✅ PASS' if functionality_success else '❌ FAIL'}")

    if is_super and import_success and functionality_success:
        print(f"\n🎉 SUCCESS: GPIO library fully functional on Super variant!")
        print(f"💡 This confirms the Super variant patch is working correctly.")
        return True
    elif not is_super:
        print(f"\n⚠️  NOTE: This is not a Super variant device")
        print(f"💡 This test is designed for Super variant hardware")
        return import_success and functionality_success
    else:
        print(f"\n❌ FAILED: GPIO library issues detected")
        print(f"💡 Check that the Super variant patch has been applied")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)