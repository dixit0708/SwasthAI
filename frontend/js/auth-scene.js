/**
 * Auth character scene — interactive mouse-tracking illustration for
 * login/register visual panels, plus password show/hide toggles.
 * Ported from https://github.com/KingWahley/interactive-login-form
 */

(function () {
  const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  function buildScene(root) {
    root.innerHTML = `
      <div class="auth-scene__stage">
        <div class="auth-char auth-char--purple" data-char="purple">
          <div class="auth-char__face">
            <span class="auth-eye"><span class="auth-eye__pupil"></span></span>
            <span class="auth-eye"><span class="auth-eye__pupil"></span></span>
          </div>
        </div>
        <div class="auth-char auth-char--black" data-char="black">
          <div class="auth-char__face">
            <span class="auth-eye"><span class="auth-eye__pupil"></span></span>
            <span class="auth-eye"><span class="auth-eye__pupil"></span></span>
          </div>
        </div>
        <div class="auth-char auth-char--orange" data-char="orange">
          <div class="auth-char__face">
            <span class="auth-pupil"></span>
            <span class="auth-pupil"></span>
          </div>
        </div>
        <div class="auth-char auth-char--yellow" data-char="yellow">
          <div class="auth-char__face">
            <span class="auth-pupil"></span>
            <span class="auth-pupil"></span>
          </div>
          <div class="auth-char__mouth"></div>
        </div>
      </div>
    `;

    return {
      purple: root.querySelector('.auth-char--purple'),
      purpleFace: root.querySelector('.auth-char--purple .auth-char__face'),
      purpleEyes: root.querySelectorAll('.auth-char--purple .auth-eye'),
      purplePupils: root.querySelectorAll('.auth-char--purple .auth-eye__pupil'),
      black: root.querySelector('.auth-char--black'),
      blackFace: root.querySelector('.auth-char--black .auth-char__face'),
      blackEyes: root.querySelectorAll('.auth-char--black .auth-eye'),
      blackPupils: root.querySelectorAll('.auth-char--black .auth-eye__pupil'),
      orange: root.querySelector('.auth-char--orange'),
      orangeFace: root.querySelector('.auth-char--orange .auth-char__face'),
      orangePupils: root.querySelectorAll('.auth-char--orange .auth-pupil'),
      yellow: root.querySelector('.auth-char--yellow'),
      yellowFace: root.querySelector('.auth-char--yellow .auth-char__face'),
      yellowPupils: root.querySelectorAll('.auth-char--yellow .auth-pupil'),
      yellowMouth: root.querySelector('.auth-char--yellow .auth-char__mouth')
    };
  }

  function calc(el, mouse) {
    if (!el) return { faceX: 0, faceY: 0, bodySkew: 0, dx: 0, dy: 0 };
    const rect = el.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 3;
    const dx = mouse.x - cx;
    const dy = mouse.y - cy;
    return {
      faceX: clamp(dx / 20, -15, 15),
      faceY: clamp(dy / 30, -10, 10),
      bodySkew: clamp(-dx / 120, -6, 6),
      dx, dy
    };
  }

  function pupilOffset(dx, dy, maxDistance) {
    const dist = Math.min(Math.hypot(dx, dy), maxDistance);
    const angle = Math.atan2(dy, dx);
    return { x: Math.cos(angle) * dist, y: Math.sin(angle) * dist };
  }

  function setPupils(pupils, offset) {
    pupils.forEach(p => {
      p.style.transform = `translate(${offset.x}px, ${offset.y}px)`;
    });
  }

  function setBlink(eyes, pupils, isBlinking) {
    eyes.forEach(eye => eye.classList.toggle('is-blinking', isBlinking));
    pupils.forEach(p => { p.style.opacity = isBlinking ? '0' : '1'; });
  }

  function scheduleBlink(setBlinking) {
    const randomMs = () => Math.random() * 4000 + 3000;
    function loop() {
      setTimeout(() => {
        setBlinking(true);
        setTimeout(() => {
          setBlinking(false);
          loop();
        }, 150);
      }, randomMs());
    }
    loop();
  }

  function initAuthScene(config) {
    const root = document.querySelector(config.scene);
    if (!root) return;

    if (prefersReducedMotion()) {
      root.classList.add('auth-scene--static');
      buildScene(root);
      return;
    }

    const els = buildScene(root);
    const emailInput = config.email ? document.querySelector(config.email) : null;
    const passwordInput = config.password ? document.querySelector(config.password) : null;

    const mouse = { x: 0, y: 0 };
    const state = {
      showPassword: false,
      passwordValue: '',
      isTyping: false,
      isLookingAtEachOther: false,
      isPurplePeeking: false,
      isPurpleBlinking: false,
      isBlackBlinking: false
    };

    let lookTimeout = null;
    let peekLoopActive = false;

    function isPeeking() {
      return state.passwordValue.length > 0 && state.showPassword;
    }

    function render() {
      const purplePos = calc(els.purple, mouse);
      const blackPos = calc(els.black, mouse);
      const orangePos = calc(els.orange, mouse);
      const yellowPos = calc(els.yellow, mouse);
      const peeking = isPeeking();
      const purpleExpanded = state.isTyping || (state.passwordValue.length > 0 && !state.showPassword);

      // Purple body
      els.purple.style.height = purpleExpanded ? '440px' : '400px';
      els.purple.style.transform = peeking
        ? 'skewX(0deg)'
        : purpleExpanded
          ? `skewX(${(purplePos.bodySkew || 0) - 12}deg) translateX(40px)`
          : `skewX(${purplePos.bodySkew || 0}deg)`;

      els.purpleFace.style.left = peeking ? '20px' : state.isLookingAtEachOther ? '55px' : `${45 + purplePos.faceX}px`;
      els.purpleFace.style.top = peeking ? '35px' : state.isLookingAtEachOther ? '65px' : `${40 + purplePos.faceY}px`;

      if (peeking) {
        const off = state.isPurplePeeking ? { x: 4, y: 5 } : { x: -4, y: -4 };
        setPupils(els.purplePupils, off);
      } else if (state.isLookingAtEachOther) {
        setPupils(els.purplePupils, { x: 3, y: 4 });
      } else {
        setPupils(els.purplePupils, pupilOffset(purplePos.dx, purplePos.dy, 5));
      }
      setBlink(els.purpleEyes, els.purplePupils, state.isPurpleBlinking && !peeking);

      // Black body
      els.black.style.transform = peeking
        ? 'skewX(0deg)'
        : state.isLookingAtEachOther
          ? `skewX(${(blackPos.bodySkew || 0) * 1.5 + 10}deg) translateX(20px)`
          : purpleExpanded
            ? `skewX(${(blackPos.bodySkew || 0) * 1.5}deg)`
            : `skewX(${blackPos.bodySkew || 0}deg)`;

      els.blackFace.style.left = peeking ? '10px' : state.isLookingAtEachOther ? '32px' : `${26 + blackPos.faceX}px`;
      els.blackFace.style.top = peeking ? '28px' : state.isLookingAtEachOther ? '12px' : `${32 + blackPos.faceY}px`;

      if (peeking) {
        setPupils(els.blackPupils, { x: -4, y: -4 });
      } else if (state.isLookingAtEachOther) {
        setPupils(els.blackPupils, { x: 0, y: -4 });
      } else {
        setPupils(els.blackPupils, pupilOffset(blackPos.dx, blackPos.dy, 4));
      }
      setBlink(els.blackEyes, els.blackPupils, state.isBlackBlinking && !peeking);

      // Orange body
      els.orange.style.transform = peeking ? 'skewX(0deg)' : `skewX(${orangePos.bodySkew || 0}deg)`;
      els.orangeFace.style.left = peeking ? '50px' : `${82 + (orangePos.faceX || 0)}px`;
      els.orangeFace.style.top = peeking ? '85px' : `${90 + (orangePos.faceY || 0)}px`;
      setPupils(els.orangePupils, peeking ? { x: -5, y: -4 } : pupilOffset(orangePos.dx, orangePos.dy, 5));

      // Yellow body
      els.yellow.style.transform = peeking ? 'skewX(0deg)' : `skewX(${yellowPos.bodySkew || 0}deg)`;
      els.yellowFace.style.left = peeking ? '20px' : `${52 + (yellowPos.faceX || 0)}px`;
      els.yellowFace.style.top = peeking ? '35px' : `${40 + (yellowPos.faceY || 0)}px`;
      setPupils(els.yellowPupils, peeking ? { x: -5, y: -4 } : pupilOffset(yellowPos.dx, yellowPos.dy, 5));
      els.yellowMouth.style.left = peeking ? '10px' : `${40 + (yellowPos.faceX || 0)}px`;
      els.yellowMouth.style.top = peeking ? '88px' : `${88 + (yellowPos.faceY || 0)}px`;
    }

    function schedulePeekPulses() {
      if (peekLoopActive) return;
      peekLoopActive = true;
      const loop = () => {
        if (!isPeeking()) { peekLoopActive = false; return; }
        setTimeout(() => {
          if (!isPeeking()) { peekLoopActive = false; return; }
          state.isPurplePeeking = true;
          render();
          setTimeout(() => {
            state.isPurplePeeking = false;
            render();
            loop();
          }, 800);
        }, Math.random() * 3000 + 2000);
      };
      loop();
    }

    window.addEventListener('mousemove', (e) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      render();
    }, { passive: true });

    if (emailInput) {
      emailInput.addEventListener('focus', () => {
        state.isTyping = true;
        state.isLookingAtEachOther = true;
        render();
        clearTimeout(lookTimeout);
        lookTimeout = setTimeout(() => {
          state.isLookingAtEachOther = false;
          render();
        }, 800);
      });
      emailInput.addEventListener('blur', () => {
        state.isTyping = false;
        render();
      });
    }

    if (passwordInput) {
      passwordInput.addEventListener('input', () => {
        state.passwordValue = passwordInput.value;
        render();
        if (isPeeking()) schedulePeekPulses();
      });
      passwordInput.addEventListener('passwordvisibilitychange', (e) => {
        state.showPassword = e.detail.visible;
        render();
        if (isPeeking()) schedulePeekPulses();
      });
    }

    scheduleBlink((v) => { state.isPurpleBlinking = v; render(); });
    scheduleBlink((v) => { state.isBlackBlinking = v; render(); });

    render();
  }

  function initPasswordToggle(buttonSelector, inputSelector) {
    const btn = document.querySelector(buttonSelector);
    const input = document.querySelector(inputSelector);
    if (!btn || !input) return;

    btn.addEventListener('click', () => {
      const visible = input.type === 'password';
      input.type = visible ? 'text' : 'password';
      btn.querySelector('i').className = visible ? 'fas fa-eye-slash' : 'fas fa-eye';
      btn.setAttribute('aria-label', visible ? 'Hide password' : 'Show password');
      input.dispatchEvent(new CustomEvent('passwordvisibilitychange', { detail: { visible } }));
    });
  }

  window.SwasthAuth = { initAuthScene, initPasswordToggle };
})();
