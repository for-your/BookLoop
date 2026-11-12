const BookLoopMotion = (() => {
  const config = Object.freeze({
    reveal: Object.freeze({ distance: 24, duration: 650, threshold: 0.08 }),
    spotlight: Object.freeze({ radius: 320, opacity: 0.55 }),
    tilt: Object.freeze({ amplitude: 6 }),
  });
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)");
  const reveals = new WeakMap();
  const pointers = new WeakMap();
  const animations = new Set();
  const observer = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      observer.unobserve(entry.target);
      const state = reveals.get(entry.target);
      if (!state || reducedMotion.matches || !entry.target.animate) return;
      const animation = entry.target.animate([
        { opacity: 0, transform: `translateY(${config.reveal.distance}px)` },
        { opacity: 1, transform: "translateY(0)" },
      ], { duration: config.reveal.duration, delay: state.delay, easing: "cubic-bezier(.22,1,.36,1)", fill: "backwards" });
      state.animation = animation;
      animations.add(animation);
      animation.onfinish = animation.oncancel = () => animations.delete(animation);
    });
  }, { threshold: config.reveal.threshold }) : null;
  reducedMotion.addEventListener("change", () => {
    if (reducedMotion.matches) animations.forEach((animation) => animation.cancel());
  });
  const reveal = {
    mounted(element, binding) {
      reveals.set(element, { delay: Math.min(Math.max(Number(binding.value) || 0, 0), 240) });
      if (!reducedMotion.matches) observer?.observe(element);
    },
    beforeUnmount(element) {
      observer?.unobserve(element);
      reveals.get(element)?.animation?.cancel();
      reveals.delete(element);
    },
  };
  function pointerEffect(kind) {
    return {
      mounted(element) {
        let frame = 0;
        const reset = () => {
          cancelAnimationFrame(frame);
          frame = 0;
          element.style.setProperty("--spot-alpha", "0");
          element.style.setProperty("--tilt-x", "0deg");
          element.style.setProperty("--tilt-y", "0deg");
        };
        const move = (event) => {
          if (!finePointer.matches || reducedMotion.matches || event.pointerType === "touch") return;
          cancelAnimationFrame(frame);
          frame = requestAnimationFrame(() => {
            const bounds = element.getBoundingClientRect();
            const horizontal = Math.min(Math.max(event.clientX - bounds.left, 0), bounds.width);
            const vertical = Math.min(Math.max(event.clientY - bounds.top, 0), bounds.height);
            if (kind === "spotlight") {
              element.style.setProperty("--spot-x", `${horizontal}px`);
              element.style.setProperty("--spot-y", `${vertical}px`);
              element.style.setProperty("--spot-alpha", String(config.spotlight.opacity));
            } else if (bounds.width && bounds.height) {
              element.style.setProperty("--tilt-x", `${(0.5 - vertical / bounds.height) * config.tilt.amplitude}deg`);
              element.style.setProperty("--tilt-y", `${(horizontal / bounds.width - 0.5) * config.tilt.amplitude}deg`);
            }
          });
        };
        const focus = () => {
          if (kind !== "spotlight") return;
          element.style.setProperty("--spot-x", "50%");
          element.style.setProperty("--spot-y", "50%");
          element.style.setProperty("--spot-alpha", String(config.spotlight.opacity));
        };
        element.style.setProperty("--spot-radius", `${config.spotlight.radius}px`);
        element.addEventListener("pointermove", move, { passive: true });
        element.addEventListener("pointerleave", reset);
        element.addEventListener("pointercancel", reset);
        element.addEventListener("focusin", focus);
        element.addEventListener("focusout", reset);
        reducedMotion.addEventListener("change", reset);
        finePointer.addEventListener("change", reset);
        pointers.set(element, () => {
          reset();
          element.removeEventListener("pointermove", move);
          element.removeEventListener("pointerleave", reset);
          element.removeEventListener("pointercancel", reset);
          element.removeEventListener("focusin", focus);
          element.removeEventListener("focusout", reset);
          reducedMotion.removeEventListener("change", reset);
          finePointer.removeEventListener("change", reset);
        });
      },
      beforeUnmount(element) {
        pointers.get(element)?.();
        pointers.delete(element);
      },
    };
  }
  return { config, reveal, spotlight: pointerEffect("spotlight"), tilt: pointerEffect("tilt") };
})();
