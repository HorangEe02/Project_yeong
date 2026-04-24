/* eslint-disable no-undef */
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: 'REPLACE_WITH_YOUR_FIREBASE_API_KEY',
  authDomain: 'mediway-demo.firebaseapp.com',
  databaseURL: 'https://mediway-demo-default-rtdb.firebaseio.com',
  projectId: 'mediway-demo',
  storageBucket: 'mediway-demo.firebasestorage.app',
  messagingSenderId: '805996216710',
  appId: '1:805996216710:web:caee81623cd2fbc5baac07',
});

const messaging = firebase.messaging();

// 백그라운드 메시지 처리
messaging.onBackgroundMessage((payload) => {
  const { title, body } = payload.notification || {};
  if (title) {
    self.registration.showNotification(title, {
      body: body || '',
      icon: '/favicon.svg',
    });
  }
});
