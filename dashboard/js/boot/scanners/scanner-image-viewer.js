// scanner-image-viewer.js — the scan preview modal: fit-to-box on load, then
// wheel zoom and pointer-drag panning inside a scrollable frame.
//
// Extracted from the scanner dialog because it is a self-contained piece of
// state (zoom level, base size, drag origin) that the scan workflow only ever
// touches through show()/hide().

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 6;
const ZOOM_STEP = 1.12;

const clampZoom = (value) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value));

export function createScannerImageViewer({
  imageBox,
  img,
  closeBtn,
  doc = document,
  win = window,
}) {
  let lastImageUrl = null;
  let zoom = 1;
  let baseWidth = 0;
  let baseHeight = 0;
  let dragging = false;
  let dragPointerId = null;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStartScrollLeft = 0;
  let dragStartScrollTop = 0;

  const canZoom = () =>
    !imageBox.classList.contains("hidden") &&
    !imageBox.classList.contains("scanner-image-loading") &&
    !imageBox.classList.contains("scanner-image-error") &&
    img.complete &&
    img.naturalWidth > 0 &&
    img.naturalHeight > 0;

  const canPan = () =>
    canZoom() &&
    (imageBox.scrollWidth > imageBox.clientWidth ||
      imageBox.scrollHeight > imageBox.clientHeight);

  const calculateBaseSize = () => {
    if (!img.naturalWidth || !img.naturalHeight) return;
    const availableWidth = Math.max(
      1,
      Math.min(imageBox.clientWidth * 0.92, 1100),
    );
    const availableHeight = Math.max(1, imageBox.clientHeight * 0.9);
    const fitScale = Math.min(
      availableWidth / img.naturalWidth,
      availableHeight / img.naturalHeight,
      1,
    );
    baseWidth = Math.max(1, Math.round(img.naturalWidth * fitScale));
    baseHeight = Math.max(1, Math.round(img.naturalHeight * fitScale));
  };

  const updateScrollMode = () => {
    const needsScroll =
      baseWidth * zoom > imageBox.clientWidth - 80 ||
      baseHeight * zoom > imageBox.clientHeight - 80;
    imageBox.classList.toggle("scanner-image-scrollable", needsScroll);
  };

  // Zoom about a point: keep whatever pixel sat under the cursor (or the box
  // centre, for programmatic zooms) under it afterwards.
  const setZoom = (nextZoom, anchorEvent = null) => {
    if (!canZoom()) return;
    if (!baseWidth || !baseHeight) calculateBaseSize();

    const boxRect = imageBox.getBoundingClientRect();
    const previousRect = img.getBoundingClientRect();
    const anchorClientX =
      anchorEvent?.clientX ?? boxRect.left + imageBox.clientWidth / 2;
    const anchorClientY =
      anchorEvent?.clientY ?? boxRect.top + imageBox.clientHeight / 2;
    const relativeX =
      previousRect.width > 0
        ? Math.min(
            1,
            Math.max(
              0,
              (anchorClientX - previousRect.left) / previousRect.width,
            ),
          )
        : 0.5;
    const relativeY =
      previousRect.height > 0
        ? Math.min(
            1,
            Math.max(
              0,
              (anchorClientY - previousRect.top) / previousRect.height,
            ),
          )
        : 0.5;

    zoom = clampZoom(nextZoom);
    img.style.width = `${Math.round(baseWidth * zoom)}px`;
    img.style.height = `${Math.round(baseHeight * zoom)}px`;
    updateScrollMode();

    requestAnimationFrame(() => {
      const nextRect = img.getBoundingClientRect();
      const contentLeft = nextRect.left - boxRect.left + imageBox.scrollLeft;
      const contentTop = nextRect.top - boxRect.top + imageBox.scrollTop;
      imageBox.scrollLeft =
        contentLeft +
        relativeX * nextRect.width -
        (anchorClientX - boxRect.left);
      imageBox.scrollTop =
        contentTop +
        relativeY * nextRect.height -
        (anchorClientY - boxRect.top);
    });
  };

  const resetZoom = () => {
    zoom = 1;
    baseWidth = 0;
    baseHeight = 0;
    imageBox.classList.remove(
      "scanner-image-ready",
      "scanner-image-scrollable",
      "scanner-image-dragging",
    );
    img.style.width = "";
    img.style.height = "";
    imageBox.scrollLeft = 0;
    imageBox.scrollTop = 0;
  };

  const stopDrag = (e) => {
    if (
      !dragging ||
      (dragPointerId !== null &&
        e?.pointerId !== undefined &&
        e.pointerId !== dragPointerId)
    ) {
      return;
    }
    dragging = false;
    dragPointerId = null;
    imageBox.classList.remove("scanner-image-dragging");
    if (e?.pointerId !== undefined && img.hasPointerCapture?.(e.pointerId)) {
      try {
        img.releasePointerCapture(e.pointerId);
      } catch {
        // Pointer capture may already be gone after cancel/lostcapture.
      }
    }
  };

  const show = (url = null) => {
    if (url) lastImageUrl = url;
    if (!lastImageUrl) return;
    // Repeated scans reuse the same filename, so cache-bust to avoid the
    // browser serving a stale/blank copy (the "shows sometimes, blank
    // sometimes" symptom). Reset src first so onload always refires.
    const bust = `${lastImageUrl}${lastImageUrl.includes("?") ? "&" : "?"}t=${Date.now()}`;
    resetZoom();
    imageBox.classList.remove("scanner-image-error");
    imageBox.classList.add("scanner-image-loading");
    img.src = "";
    img.src = bust;
    imageBox.classList.remove("hidden");
  };

  const hide = () => {
    stopDrag();
    imageBox.classList.add("hidden");
  };

  img.addEventListener("load", () => {
    imageBox.classList.remove("scanner-image-loading", "scanner-image-error");
    imageBox.classList.add("scanner-image-ready");
    calculateBaseSize();
    setZoom(1);
  });
  img.addEventListener("error", () => {
    imageBox.classList.remove("scanner-image-loading");
    imageBox.classList.add("scanner-image-error");
    imageBox.classList.remove(
      "scanner-image-ready",
      "scanner-image-scrollable",
      "scanner-image-dragging",
    );
  });

  closeBtn.addEventListener("click", hide);
  // Click the dark backdrop (outside the image frame) to close the modal.
  imageBox.addEventListener("click", (e) => {
    if (e.target === imageBox) hide();
  });
  img.addEventListener("pointerdown", (e) => {
    if (e.button !== 0 || !canPan()) return;
    e.preventDefault();
    dragging = true;
    dragPointerId = e.pointerId;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragStartScrollLeft = imageBox.scrollLeft;
    dragStartScrollTop = imageBox.scrollTop;
    imageBox.classList.add("scanner-image-dragging");
    try {
      img.setPointerCapture?.(e.pointerId);
    } catch {
      // Synthetic pointer events may not be eligible for capture.
    }
  });
  img.addEventListener("pointermove", (e) => {
    if (!dragging || e.pointerId !== dragPointerId) return;
    e.preventDefault();
    imageBox.scrollLeft = dragStartScrollLeft - (e.clientX - dragStartX);
    imageBox.scrollTop = dragStartScrollTop - (e.clientY - dragStartY);
  });
  img.addEventListener("pointerup", stopDrag);
  img.addEventListener("pointercancel", stopDrag);
  img.addEventListener("lostpointercapture", stopDrag);
  imageBox.addEventListener(
    "wheel",
    (e) => {
      if (!canZoom()) return;
      e.preventDefault();
      setZoom(zoom * (e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP), e);
    },
    { passive: false },
  );
  win.addEventListener("resize", () => {
    if (!canZoom()) return;
    calculateBaseSize();
    setZoom(zoom);
  });
  doc.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !imageBox.classList.contains("hidden")) hide();
  });

  return { show, hide };
}
