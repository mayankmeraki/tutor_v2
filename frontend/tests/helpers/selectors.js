/**
 * Central selector map — single source of truth for all test selectors.
 * Grouped by screen/feature.
 */

export const SEL = {
  // ─── Screens ─────────────────────────────────────────────
  screens: {
    landing: '#landing-screen',
    business: '#business-screen',
    login: '#login-panel',
    browse: '#browse-screen',
    course: '#course-screen',
    ondemand: '#ondemand-screen',
    teaching: '#teaching-layout',
  },

  // ─── Landing ─────────────────────────────────────────────
  landing: {
    heroInput: '#lp-hero-input',
    heroBtn: '#lp-hero-btn',
    signIn: '#lp-signin',
    getStarted: '#lp-getstarted',
    logo: '.sc-logo',
    forBusiness: 'a[href="/for-business"]',
  },

  // ─── Auth ────────────────────────────────────────────────
  auth: {
    tabSignIn: '[data-tab="signin"]',
    tabSignUp: '[data-tab="signup"]',
    loginEmail: '#login-email',
    loginPassword: '#login-password',
    loginBtn: '#btn-login',
    loginStatus: '#login-status',
    signupName: '#signup-name',
    signupEmail: '#signup-email',
    signupPassword: '#signup-password',
    signupBtn: '#btn-signup',
    signupStatus: '#signup-status',
  },

  // ─── Home / Browse ──────────────────────────────────────
  home: {
    greeting: '#browse-greeting',
    eulerInput: '#euler-input',
    eulerSendBtn: '#euler-send-btn',
    eulerChips: '#euler-chips .euler-chip',
    logoutBtn: '#btn-logout',
    avatar: '#dash-avatar',
    userName: '#dash-user-name',
    tabHome: '[data-home-tab="home"]',
    tabStuff: '[data-home-tab="stuff"]',
    sessionsSection: '#home-sessions-section',
    sessionsRow: '#home-sessions-row',
    coursesSection: '#home-courses-section',
    coursesGrid: '#home-courses-grid',
    videosSection: '#home-videos-section',
    videosRow: '#home-videos-row',
    collectionsBtn: '#btn-new-collection',
    collectionsList: '#collections-list',
  },

  // ─── Course Detail ──────────────────────────────────────
  course: {
    backBtn: '#cd-back',
    title: '#cd-title',
    description: '#cd-description',
    playBtn: '#cd-play-btn',
    lessonsCount: '#cd-lessons-count',
    modulesCount: '#cd-modules-count',
    hours: '#cd-hours',
    filmstrip: '#cd-filmstrip',
    lessonDetail: '#cd-lesson-detail',
    detailTitle: '#cd-detail-title',
    banner: '#cd-banner',
    tag: '#cd-tag',
  },

  // ─── Teaching Layout ────────────────────────────────────
  teaching: {
    topBar: '#top-bar',
    backBtn: '#btn-back',
    courseTitle: '#course-title',
    timer: '#session-timer',
    cost: '#session-cost',
    mainLayout: '#main-layout',
    chatPanel: '#chat-panel',
    canvasStream: '#canvas-stream',
    boardPanel: '#board-panel',
    spotlightContent: '#spotlight-content',
    boardEmpty: '#board-empty-state',
    speedBtn: '#speed-toggle-btn',
    speedVal: '#speed-val',
    speedMenu: '#speed-menu',
    prepOverlay: '#session-prep-overlay',
    prepMsg: '#session-prep-msg',
  },

  // ─── Voice UI ───────────────────────────────────────────
  voice: {
    subtitle: '#voice-subtitle-text',
    indicator: '#voice-indicator',
    micFloat: '#voice-mic-float',
    barInput: '#voice-bar-input',
    barPause: '#voice-bar-pause',
    barResume: '#voice-bar-resume',
    barStop: '#voice-bar-stop',
    micBtn: '#voice-mic-btn',
    barSend: '#voice-bar-send',
    hand: '#voice-hand-cursor',
    progress: '#vb-progress',
    status: '#vb-status',
  },

  // ─── Video Follow-Along ─────────────────────────────────
  video: {
    overlay: '#vm-video-overlay',
    closeBtn: '#vm-close-btn',
    vidWrap: '#vm-vid-wrap',
    chatWrap: '#vm-chat-wrap',
    chatInput: '#vm-chat-input',
    sendBtn: '#vm-send-btn',
    stopBtn: '#vm-stop-btn',
    playlist: '#video-playlist',
    playlistList: '#vpl-list',
    playlistCount: '#vpl-count',
  },

  // ─── Plan ───────────────────────────────────────────────
  plan: {
    headingBar: '#plan-heading-bar',
    panel: '#plan-panel',
    panelClose: '#plan-panel-close',
    panelBody: '#plan-panel-body',
    sidebar: '#plan-sidebar',
    sidebarToggle: '#psb-toggle',
  },

  // ─── Feedback Modal ─────────────────────────────────────
  feedback: {
    overlay: '#fb-overlay',
    form: '#fb-form',
    submitBtn: '#fb-submit',
  },

  // ─── Simulation ─────────────────────────────────────────
  simulation: {
    overlay: '#sim-fullscreen-overlay',
    closeBtn: '#sim-fullscreen-close',
    iframe: '#sim-fullscreen-iframe',
  },
};
