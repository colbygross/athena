// Lets non-button elements with onClick respond to Enter and Space like a real button.
export const activateOnKey = (e) => {
  if (e.target !== e.currentTarget) return;
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    e.currentTarget.click();
  }
};
