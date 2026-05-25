import pyrealsense2 as rs
import numpy as np
import cv2
import os

## https://github.com/jetsonhacks/jetson-orin-librealsense camera library for jetson devices. It is a wrapper around the Intel Realsense SDK.
## The code is adapted from the librealsense examples and modified to include spatial filtering, hole filling, and a simple obstacle detection algorithm based on dividing the depth image into 6 segments and checking
## testing code https://github.com/carlosefrias/realsense-t265-and-d435-testing/blob/master/Python/realsenseD435_stream.py

def image_file_counter(path):
    files = 0
    for _, _, filenames in os.walk(path):
        files += len(filenames)
    return files + 1


def spatial_filtering(depth_frame, magnitude=2, alpha=0.5, delta=20, holes_fill=0):
    spatial = rs.spatial_filter()
    spatial.set_option(rs.option.filter_magnitude, magnitude)
    spatial.set_option(rs.option.filter_smooth_alpha, alpha)
    spatial.set_option(rs.option.filter_smooth_delta, delta)
    spatial.set_option(rs.option.holes_fill, holes_fill)
    depth_frame = spatial.process(depth_frame)
    return depth_frame


def hole_filling(depth_frame):
    hole_filling = rs.hole_filling_filter()
    depth_frame = hole_filling.process(depth_frame)
    return depth_frame

def check_blocked(depth_roi, depth_scale, threshold_m=1.0):
    """
    Check if a region of interest (ROI) is blocked.
    Calculates the median depth of valid pixels and compares it to the threshold.
    """
    dist_m = depth_roi * depth_scale
    valid_dist = dist_m[dist_m > 0]
    
    if len(valid_dist) < (depth_roi.size * 0.1):
        # Too little valid data, assume blocked/too close for safety
        return True
        
    median_dist = np.median(valid_dist)
    return median_dist < threshold_m

# define global variables
# ========================
# file names and paths
rgb_img_path = 'captured_images/rgb_image/'
depth_img_path = 'captured_images/depth_image/'
colored_depth_img_path = 'captured_images/coloured_depth_image/'
intrinsics = True
rotate_camera = False


if __name__ == "__main__":
        # ========================
    # 1. Configure all streams
    # ========================
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

    # ======================
    # 2. Start the streaming
    # ======================
    print("Starting up the Intel Realsense D435...")
    print("")
    profile = pipeline.start(config)

    # =================================
    # 3. The depth sensor's depth scale
    # =================================
    depth_sensor = profile.get_device().first_depth_sensor()
    depth_scale = depth_sensor.get_depth_scale()
    print("Depth Scale is: ", depth_scale)
    print("")

    # ==========================================
    # 4. Create an align object.
    #    Align the depth image to the rgb image.
    # ==========================================
    align_to = rs.stream.color
    align = rs.align(align_to)

    try:
        # ===========================================
        # 5. Skip the first 30 frames.
        # This gives the Auto-Exposure time to adjust
        # ===========================================
        for x in range(30):
            frames = pipeline.wait_for_frames()
            # Align the depth frame to color frame
            aligned_frames = align.process(frames)

        print("Intel Realsense D435 started successfully.")
        print("")

        while True:
            # ======================================
            # 6. Wait for a coherent pair of frames:
            # ======================================
            frames = pipeline.wait_for_frames()

            # =======================================
            # 7. Align the depth frame to color frame
            # =======================================
            aligned_frames = align.process(frames)

            # ================================================
            # 8. Fetch the depth and colour frames from stream
            # ================================================
            depth_frame = aligned_frames.get_depth_frame()
            color_frame = aligned_frames.get_color_frame()
            if not depth_frame or not color_frame:
                continue

            # print the camera intrinsics just once. it is always the same
            if intrinsics:
                print("Intel Realsense D435 Camera Intrinsics: ")
                print("========================================")
                print(depth_frame.profile.as_video_stream_profile().intrinsics)
                print(color_frame.profile.as_video_stream_profile().intrinsics)
                print("")
                intrinsics = False

            # =====================================
            # 9. Apply filtering to the depth image
            # =====================================
            # Apply a spatial filter without hole_filling (i.e. holes_fill=0)
            depth_frame = spatial_filtering(depth_frame, magnitude=2, alpha=0.5, delta=50, holes_fill=0)
            # Apply hole filling filter
            depth_frame = hole_filling(depth_frame)

            # ===========================
            # 10. colourise the depth map
            # ===========================
            depth_color_frame = rs.colorizer().colorize(depth_frame)

            # ==================================
            # 11. Convert images to numpy arrays
            # ==================================
            depth_image = np.array(depth_frame.get_data())
            depth_color_image = np.asanyarray(depth_color_frame.get_data())
            color_image = np.asanyarray(color_frame.get_data())

            # ======================================================================
            # 12. Only rotate the images if the realsense camera is placed vertical.
            # Otherwise set the variable "rotate_camera = False"
            # ======================================================================
            if rotate_camera:
                depth_image = np.rot90(depth_image)
                depth_color_image = np.rot90(depth_color_image)
                color_image = np.rot90(color_image)

            # ==============================================
            # 13. Create Dynamic Grid and Calculate Obstacles
            # ==============================================
            h, w = depth_image.shape
            ROWS, COLS = 4, 5
            w_step = w // COLS
            h_step = h // ROWS

            # Create a 2D list to store block statuses
            blocked_grid = [[False for _ in range(COLS)] for _ in range(ROWS)]

            # Check if each segment is blocked (Threshold is 1.0 meters)
            for r in range(ROWS):
                for c in range(COLS):
                    y_start, y_end = r * h_step, (r + 1) * h_step if r < ROWS - 1 else h
                    x_start, x_end = c * w_step, (c + 1) * w_step if c < COLS - 1 else w
                    
                    segment = depth_image[y_start:y_end, x_start:x_end]
                    blocked_grid[r][c] = check_blocked(segment, depth_scale, 1.0)

            # Determine Action based on rules
            # We adapt previous rules to the new grid scale:
            total_blocks = sum([sum(row) for row in blocked_grid])
            bottom_row_blocked = sum(blocked_grid[-1]) >= (COLS - 1)  # Most of bottom row is blocked
            
            # Check left columns (e.g. columns 0 and 1)
            left_blocks = sum([blocked_grid[r][c] for r in range(ROWS) for c in range(2)])
            # Check right columns (e.g. columns COLS-2 and COLS-1)
            right_blocks = sum([blocked_grid[r][c] for r in range(ROWS) for c in range(COLS-2, COLS)])

            action = "HOVER"
            
            if total_blocks >= (ROWS * COLS) - 3:  # Almost all strictly blocked
                action = "MOVE BACK"
            elif bottom_row_blocked:
                action = "MOVE UP"
            elif left_blocks > right_blocks and left_blocks >= ROWS:
                action = "MOVE RIGHT"
            elif right_blocks > left_blocks and right_blocks >= ROWS:
                action = "MOVE LEFT"

            print(f"Decision: {action} | Blocks: {total_blocks}/{ROWS*COLS} | Left: {left_blocks} Right: {right_blocks} Bot: {sum(blocked_grid[-1])}")

            # Draw lines and text for regions in both color and depth_color
            for img in (color_image, depth_color_image):
                # Vertical lines
                for c in range(1, COLS):
                    cv2.line(img, (c * w_step, 0), (c * w_step, h), (255, 255, 255), 1)
                # Horizontal lines
                for r in range(1, ROWS):
                    cv2.line(img, (0, r * h_step), (w, r * h_step), (255, 255, 255), 1)

            def put_status(img, blocked, pt):
                text = "X" if blocked else "O"
                color = (0, 0, 255) if blocked else (0, 255, 0)
                # Small text for tighter grids
                cv2.putText(img, text, pt, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            for r in range(ROWS):
                for c in range(COLS):
                    put_status(color_image, blocked_grid[r][c], (c * w_step + 10, r * h_step + 25))

            cv2.putText(color_image, f"ACTION: {action}", (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 3)

            # Stack rgb and depth map images horizontally for visualisation only
            images = np.hstack((color_image, depth_color_image))

            # Show horizontally stacked rgb and depth map images
            cv2.namedWindow('RGB and Depth Map Images')
            cv2.imshow('RGB and Depth Map Images', images)
            c = cv2.waitKey(1)

            # =============================================
            # If the 's' key is pressed, we save the images
            # =============================================
            if c == ord('s'):
                img_counter = image_file_counter(rgb_img_path)

                '''create a stream folders'''
                if not os.path.exists(rgb_img_path):
                    os.makedirs(rgb_img_path)
                if not os.path.exists(depth_img_path):
                    os.makedirs(depth_img_path)
                if not os.path.exists(colored_depth_img_path):
                    os.makedirs(colored_depth_img_path)

                filename = str(img_counter) + '.png'
                filename_raw = str(img_counter) + '.raw'
                # save the rgb colour image
                cv2.imwrite(os.path.join(rgb_img_path, filename), color_image)
                # Save the depth image in raw binary format uint16.
                f = open(os.path.join(depth_img_path, filename_raw), mode='wb')
                depth_image.tofile(f)
                cv2.imwrite(os.path.join(colored_depth_img_path, filename), depth_color_image)

                print('images have been successfully saved')

            elif c == 27:  # esc to exit
                break

    finally:
        # Stop streaming
        pipeline.stop()