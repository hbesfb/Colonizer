document.addEventListener('DOMContentLoaded', () => {
   // zoom in on image on click
   document.getElementById('zoom').addEventListener('click', fullscreen);
   document.getElementById('overlay').addEventListener('dblclick', fullscreen);
});

function fullscreen() {
   const wrapper = document.getElementById('fullscreen-wrapper');
   const icon = document.querySelector('#zoom svg');

   if (!document.fullscreenElement) {
      // Enter fullscreen on the wrapper
      wrapper.requestFullscreen().catch(err => {
         console.warn(`Error attempting to enable fullscreen: ${err.message}`);
      });
      icon.classList.replace('fa-search-plus', 'fa-search-minus');
   } else {
      // Exit fullscreen
      document.exitFullscreen();
      icon.classList.replace('fa-search-minus', 'fa-search-plus');
   }
}
