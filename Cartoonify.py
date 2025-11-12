import cv2
import numpy as np

# Load image
img = cv2.imread(r'C:\Users\steve\Desktop\Screenshot 2025-11-09 154424.png')

# --- Step 1: Cartoon effect (same as before) ---
color = cv2.bilateralFilter(img,
    d=3, # Diameter of neighborhood in pixels: smaller = more detail
    sigmaColor=100, # Color Variation: smaller = preserved color detail
    sigmaSpace=100 # Pixel distance influence: smaller = local smoothing
)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
gray = cv2.medianBlur(gray, 1) # Kernel size: Larger = stronger blur
edges = cv2.adaptiveThreshold(
    gray, 255,
    cv2.ADAPTIVE_THRESH_MEAN_C,
    cv2.THRESH_BINARY,
    blockSize=9, # Size to calculate threshold: smaller = more small edges
    C=9 # Constant subtracted from mean: Higher = more black
)
cartoon = cv2.bitwise_and(color, color, mask=edges)

# Show results
cv2.imshow("Original", img)
cv2.imshow("Cartoon", cartoon)
cv2.waitKey(0)
cv2.destroyAllWindows()
