document.addEventListener('DOMContentLoaded', () => {
    const joinGroupForm = document.getElementById('joinGroupForm');
    if (joinGroupForm) {
        joinGroupForm.addEventListener('submit', function (event) {
            event.preventDefault();
            const form = event.target;
            const card = form.closest('.open-group-form');
            const groupIdOrUrl = document.getElementById('groupIdInput').value.trim();

            if (groupIdOrUrl) {
                if (card) {
                    card.style.transition = "transform 0.3s ease, opacity 0.3s ease";
                    card.style.transform = "scale(0.95)";
                    card.style.opacity = "0";
                }

                setTimeout(() => {
                    let groupId = groupIdOrUrl.split("=").pop();
                    window.location.href = "/group?groupId=" + groupId;
                }, 300);
            }
        });
    }
});
