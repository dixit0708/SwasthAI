/* Adapts-to-you circular gallery
   Arranges the health-category cards on a 3D ring, auto-rotates it slowly,
   and lets visitors drag (mouse or touch) to spin it manually. */
(function () {
    'use strict';

    function initAdaptsGallery() {
        var viewport = document.getElementById('adaptsGalleryViewport');
        var stage = document.getElementById('adaptsGalleryStage');
        if (!viewport || !stage) return;

        var cards = Array.prototype.slice.call(stage.querySelectorAll('.adapts-card'));
        var count = cards.length;
        if (!count) return;

        var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function getRadius() {
            var value = getComputedStyle(viewport).getPropertyValue('--radius');
            var parsed = parseFloat(value);
            return isNaN(parsed) ? 275 : parsed;
        }

        function layout() {
            var radius = getRadius();
            var step = 360 / count;
            cards.forEach(function (card, i) {
                card.style.transform = 'rotateY(' + (i * step) + 'deg) translateZ(' + radius + 'px)';
            });
        }

        layout();
        window.addEventListener('resize', layout);

        var rotation = 0;
        var autoSpeed = reducedMotion ? 0 : 0.14; // degrees per frame (~8.4deg/s at 60fps)
        var hoverPaused = false;
        var dragging = false;
        var pointerId = null;
        var startX = 0;
        var startRotation = 0;
        var lastX = 0;
        var lastTime = 0;
        var velocity = 0; // deg per ms, from drag flicks
        var resumeTimer = null;

        function applyRotation() {
            stage.style.transform = 'rotateY(' + rotation + 'deg)';
        }

        function tick() {
            if (!dragging) {
                if (Math.abs(velocity) > 0.001) {
                    rotation += velocity * 16;
                    velocity *= 0.94;
                } else if (!hoverPaused) {
                    rotation += autoSpeed;
                }
                applyRotation();
            }
            requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);

        function scheduleResume() {
            clearTimeout(resumeTimer);
            resumeTimer = setTimeout(function () {
                velocity = 0;
            }, 1200);
        }

        function onPointerDown(e) {
            dragging = true;
            velocity = 0;
            pointerId = e.pointerId;
            startX = e.clientX;
            lastX = e.clientX;
            lastTime = performance.now();
            startRotation = rotation;
            viewport.setPointerCapture(pointerId);
            clearTimeout(resumeTimer);
        }

        function onPointerMove(e) {
            if (!dragging || e.pointerId !== pointerId) return;
            var deltaX = e.clientX - startX;
            var sensitivity = 0.28;
            rotation = startRotation + deltaX * sensitivity;
            applyRotation();

            var now = performance.now();
            var dt = now - lastTime;
            if (dt > 0) {
                velocity = ((e.clientX - lastX) * sensitivity) / dt;
            }
            lastX = e.clientX;
            lastTime = now;
        }

        function onPointerUp(e) {
            if (!dragging || e.pointerId !== pointerId) return;
            dragging = false;
            try { viewport.releasePointerCapture(pointerId); } catch (err) { /* noop */ }
            scheduleResume();
        }

        viewport.addEventListener('pointerdown', onPointerDown);
        viewport.addEventListener('pointermove', onPointerMove);
        viewport.addEventListener('pointerup', onPointerUp);
        viewport.addEventListener('pointercancel', onPointerUp);
        viewport.addEventListener('pointerleave', function (e) {
            if (dragging && e.pointerId === pointerId) onPointerUp(e);
        });

        // Pause auto-rotation while hovered on desktop; resume on mouse leave.
        viewport.addEventListener('mouseenter', function () { hoverPaused = true; });
        viewport.addEventListener('mouseleave', function () { hoverPaused = false; });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAdaptsGallery);
    } else {
        initAdaptsGallery();
    }
})();
