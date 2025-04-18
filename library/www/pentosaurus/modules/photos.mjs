// NOTE: Make sure the url in the `<link rel="preload" …>` line in
// photos/index.html matches this one:
const s3_bucket_endpoint = "https://pentosaurus-assets.fly.storage.tigris.dev/photos"

async function loadManifest() {
  const response = await fetch(`${s3_bucket_endpoint}/manifest.json`);
  if (!response.ok) {
    throw new Error(`Failed to load images manifest: ${response.status} ${response.statusText}`);
  }
  const manifest = await response.json();
  return manifest;
}

loadManifest()
  .then(manifest => {
    // NOTE: Make sure this corresponds to the "default" image set in the
    // viewer. As of writing index 1 corresponds to the image "fullsize-15"
    // in `manifest.json`:
    var gallery_index = 1;

    console.log("Fetched images manifest");

    if (!manifest.images || !Array.isArray(manifest.images) || manifest.images.length === 0) {
      console.error("Invalid manifest schema: expected a non-empty 'images' array.");
      return;
    }

    const gallery = document.querySelector(".gallery");
    if (!gallery) {
      console.error("gallery div not found");
      return;
    }

    // For each image entry in the manifest, create an image element
    manifest.images.forEach(image => {
      // Construct the URL for the thumbnail image using the entry's name
      const thumbUrl = `${s3_bucket_endpoint}/${image.name}/thumb.jpg`;
      const imgElement = document.createElement("img");
      imgElement.src = thumbUrl;
      imgElement.addEventListener("click", () => { updateViewer(viewer, image); });
      gallery.appendChild(imgElement);
    });
    console.log(`Loaded ${manifest.images.length} images`);

    const viewer = document.querySelector(".viewer");
    if (!viewer) {
      console.error("viewer not found");
      return;
    }
    const left_arrow = viewer.querySelector("div:nth-of-type(1)");
    const right_arrow = viewer.querySelector("div:nth-of-type(2)");
    if (!left_arrow || !right_arrow) {
      console.error("viewer control arrows not found");
      return;
    }
    left_arrow.addEventListener("click", () => {
      gallery_index = decrIndex(manifest, gallery_index);
      updateViewer(viewer, manifest.images[gallery_index]);
    });
    right_arrow.addEventListener("click", () => {
      gallery_index = incrIndex(manifest, gallery_index);
      updateViewer(viewer, manifest.images[gallery_index]);
    });

    var touch_start_x = 0;
    var is_zooming = false;
    const swipe_threshold = 50; // Minimum horizontal distance (in pixels) to consider it a swipe
    const passive_event_listener = {passive: true};
    viewer.addEventListener("touchstart", (event) => {
      is_zooming = event.touches.length > 1;
      touch_start_x = event.changedTouches[0].screenX;
    }, passive_event_listener);
    viewer.addEventListener("touchend", (event) => {
      if (is_zooming || event.changedTouches.length > 1) {
        return;
      }
      const touch_end_x = event.changedTouches[0].screenX;
      const swipe_distance = touch_end_x - touch_start_x;
      if (Math.abs(swipe_distance) < swipe_threshold) {
        return;
      }
      if (swipe_distance < 0) {
        // Swiped left: move to the next image
        gallery_index = incrIndex(manifest, gallery_index);
      } else {
        // Swiped right: move to the previous image
        gallery_index = decrIndex(manifest, gallery_index);
      }
      updateViewer(viewer, manifest.images[gallery_index]);
    }, passive_event_listener);

    document.addEventListener("keydown", (event) => {
      // Check if no input or textarea is focused to avoid interfering with typing.
      if (document.activeElement.tagName === "INPUT" || document.activeElement.tagName === "TEXTAREA") {
        return;
      }

      if (event.key === "ArrowLeft" || event.key.toLowerCase() === "h") {
        gallery_index = decrIndex(manifest, gallery_index);
        updateViewer(viewer, manifest.images[gallery_index]);
      } else if (event.key === "ArrowRight" || event.key.toLowerCase() === "l") {
        gallery_index = incrIndex(manifest, gallery_index);
        updateViewer(viewer, manifest.images[gallery_index]);
      }
    })

  })
  .catch(error => console.error("Error loading manifest:", error));

function incrIndex(manifest, index) {
  return (index + 1) % manifest.images.length;
}

function decrIndex(manifest, index) {
  return (index - 1 + manifest.images.length) % manifest.images.length;
}

function updateViewer(viewer, image) {
  const useHalf = window.innerWidth <= image.width / 2 || window.innerHeight <= image.height / 2;
  const resolution = useHalf ? "half" : "full";
  const picture = viewer.querySelector("picture");
  picture.querySelectorAll("source").forEach(source => source.remove());
  const img = viewer.querySelector("img");
  img.id = "";
  img.src = `${s3_bucket_endpoint}/${image.name}/${resolution}.jpg`;
}
