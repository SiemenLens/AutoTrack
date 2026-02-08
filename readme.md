# AutoTrack

**AutoTrack** streamlines the VFX workflow by automating the tedious process of 2D feature tracking and camera solving. It uses **smart logic** to track markers forwards and backwards, analyzes track density on a substep level, and uses a **dual-pass solver** to find the best possible reconstruction error.

### Key Features

*   **Automated Smart Substep Tracking:** Breaks long clips into substeps to ensure tracking stability across the entire shot.
*   **Smart Filtering:** A brand new algorithm that analyzes tracks on a substep level. It actively prevents "bald spots" in your tracking data and ensures optimal marker density is maintained across the entire shot.
*   **Dual-Pass Solving:** Usually achieves 1px or lower accuracy by running an initial solve, using that data to automatically clean up bad tracks, and then performing a final high-precision solve.
*   **Annotation Masks:** Use the Grease Pencil / Annotation tool to draw zones. You can choose to either **exclude** markers in that zone (e.g., moving actors) or **only** track inside that zone.
*   **Sensor Presets:** Quickly select sensor sizes for common cameras (Full Frame, Crop Sensor, MFT, Smartphones) without needing to look up dimensions.
*   **Tripod Mode:** Dedicated solver mode for tripod/nodal pans.
*   **Solve Refining:** Automatically refine your track's focal length and radial distortion using multiple solve iterations. The UI automatically updates to reflect the refined focal length.
*   **Surface Generator:** Instantly turn your point cloud into projected surfaces. You can now tweak the generation settings (Resolution, Radius) directly from the AutoTrack panel.
*   **Custom Lens Settings:** Know your exact optical center and radial distortion? You can input custom lens data in the Solver tab to replace default values.
*   **Integrated Updates:** Check for and install new versions of the add-on directly from the About page.

### How to Use

1.  Open the **Movie Clip Editor**.
2.  Load your footage.
3.  Open the Sidebar (`N` key) and click on the **AutoTrack** tab.
4.  Adjust settings (such as Focal Length) and click **Start Tracking!**

The add-on will handle the rest, providing status updates as it tracks, filters, and solves the scene.

After the tracking & solving is finished, you can tweak the **Surface Generator** directly in the panel. You can also still tweak the focal length using the Quick Resolve option!

### Feature Requests & Feedback
Please feel free to do feature requests either in the reviews of this addon, send them to me personally or join the [Discord Support Server](https://discord.gg/QRt4VQDHxX)!

### Donations
Want to donate? You can do so on my [PayPal](https://www.paypal.me/shop10designs). Donations are greatly appreciated and will aid me to continuously improve this add-on.