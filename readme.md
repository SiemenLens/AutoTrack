# AutoTrack

**AutoTrack** streamlines the VFX workflow in Blender by automating the tedious process of 2D feature tracking, camera solving, and object tracking. It uses **smart substep logic** to track markers forwards and backwards, intelligently balances track density across shots, and uses a **dual-pass solver** to achieve the lowest possible reconstruction error.

### Key Features

*   **Automated Smart Substep Tracking:** Automatically divides long clips into dynamic substeps to prevent marker drift and ensure rock-solid tracking stability across the shot.
*   **Object Tracking (Beta):** Full support for tracking moving objects in your footage. Add, select, and manage tracking objects directly from the AutoTrack sidebar, automatically link them to 3D scene objects via smart constraints, and adjust their depth with the built-in **Distance (Scale)** slider.
*   **Per-Object Annotation Masks:** Draw zones with Blender’s Annotation tool to either **exclude** problematic areas (e.g., moving actors, reflections) or **only** track specific regions. Masks dynamically sync and switch per tracking object to prevent masking conflicts.
*   **Smart Filtering:** A specialized filtering algorithm that analyzes tracks on a substep level. It actively prevents "bald spots" in your tracking data while ensuring optimal marker density across the entire timeline.
*   **Dual-Pass Solving:** Consistently targets sub-pixel accuracy (often 1px or lower) by running an initial solve, filtering out bad tracks based on reprojection error, and performing a final high-precision solve.
*   **Surface Generator:** Instantly turn your solved point clouds into textured, reprojected 3D surfaces with a single click. Works for both camera environments and moving object tracks, with interactive controls for mesh resolution and connection radius right in the sidebar.
*   **Marker Placement Preview (Test Markers):** Preview how your threshold, scale, and distance settings will distribute trackers on the current frame before committing to a full tracking run.
*   **Solve Refining & Custom Lens Settings:** Refine focal length and radial distortion across multiple solve passes. Have precise calibration data? You can input custom optical center and radial distortion (K1, K2, K3) parameters directly.
*   **Sensor Presets:** Quickly select sensor sizes for common cameras (Full Frame, Crop Sensor, Micro Four Thirds, Smartphones, or Custom) without looking up physical dimensions.
*   **Tripod Mode:** Dedicated solver mode for nodal/tripod pans and stationary camera rotations.
*   **Quick Resolve:** Re-calculate the solve instantly after tweaking focal length, sensor sizes, or tripod settings without having to re-track footage from scratch.
*   **Audio Completion Alert:** Get an optional sound notification when a long tracking and solving operation finishes, so you can multitask freely.

---

### How to Use

#### Camera Tracking:
1. Open the **Movie Clip Editor** and load your footage.
2. Open the Sidebar (`N` key) and switch to the **AutoTrack** tab.
3. Set your Camera Sensor and approximate Focal Length (or leave defaults and enable *Refine Focal Length*).
4. *(Optional)* Draw an annotation mask on your footage and choose **Exclude** or **Only**.
5. Click **Start Camera Tracking!**

#### Object Tracking:
1. Make sure your **Camera** is tracked and solved first.
2. Expand the **Object Tracking (Beta)** panel and click **Add Object Track**.
3. Select your object in the list and draw an annotation mask over the object to isolate tracking markers.
4. Click **Start [ObjectName] Tracking!**.
5. Assign a target 3D object from your scene under **Linked Object** and tweak the **Distance (Scale)** slider to place it accurately in camera space.

After solving, use the **Surface Generator** to create projection-mapped geometry for rapid scene reconstruction and holdouts.

---

### Feature Requests & Feedback
Got an idea or ran into an issue? Report bugs on [GitHub Issues](https://github.com/SiemenLens/AutoTrack/issues) or join the community on the [Discord Support Server](https://discord.gg/QRt4VQDHxX)!

### Donations
Want to support development? You can donate via [PayPal](https://www.paypal.me/shop10designs). Support directly aids continuous development and future updates!
