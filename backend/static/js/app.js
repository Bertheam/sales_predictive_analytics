document.addEventListener("DOMContentLoaded", () => {
  const flashMessages = document.querySelectorAll("#flash-messages [data-message]");
  const levelIcons = { success: "success", error: "error", warning: "warning", info: "info" };

  flashMessages.forEach((item) => {
    if (!window.Swal) {
      item.className = `notice ${item.dataset.level || "info"}`;
      item.textContent = item.dataset.message;
      item.parentElement.hidden = false;
      return;
    }
    window.Swal.fire({
      toast: true,
      position: "top-end",
      icon: levelIcons[item.dataset.level] || "info",
      title: item.dataset.message,
      showConfirmButton: false,
      timer: 3800,
      timerProgressBar: true,
    });
  });

  if (window.jQuery?.fn?.select2) {
    window.jQuery("select:not([data-native-select])").each(function initializeSelect() {
      const select = window.jQuery(this);
      if (this.closest(".swal2-container") || select.hasClass("swal2-select")) return;
      if (!select.hasClass("select2-hidden-accessible")) {
        select.select2({
          width: "100%",
          placeholder: select.data("placeholder") || undefined,
          allowClear: Boolean(select.data("allow-clear")),
          language: {
            noResults: () => "Aucun résultat",
            searching: () => "Recherche…",
          },
        });
      }
    });
  }

  document.querySelectorAll("form[data-confirm-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      if (form.dataset.confirmed === "true") return;
      event.preventDefault();
      const title = form.dataset.confirmTitle || "Confirmer cette action ?";
      const text = form.dataset.confirmText || "";
      if (!window.Swal) {
        if (window.confirm(title)) {
          form.dataset.confirmed = "true";
          form.requestSubmit();
        }
        return;
      }
      const result = await window.Swal.fire({
        title,
        text,
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Confirmer",
        cancelButtonText: "Annuler",
        reverseButtons: true,
        customClass: { confirmButton: "swal-confirm", cancelButton: "swal-cancel" },
      });
      if (result.isConfirmed) {
        form.dataset.confirmed = "true";
        form.requestSubmit();
      }
    });
  });

  document.addEventListener("click", (event) => {
    document.querySelectorAll("details.user-dropdown[open]").forEach((dropdown) => {
      if (!dropdown.contains(event.target)) dropdown.removeAttribute("open");
    });
    document.querySelectorAll("details.company-picker[open]").forEach((dropdown) => {
      if (!dropdown.contains(event.target)) dropdown.removeAttribute("open");
    });
    document.querySelectorAll("details.mobile-more[open]").forEach((dropdown) => {
      if (!dropdown.contains(event.target)) dropdown.removeAttribute("open");
    });
  });

  const autoRefresh = document.querySelector("[data-auto-refresh-url]");
  if (autoRefresh) {
    const delay = Number(autoRefresh.dataset.autoRefreshDelay || 8000);
    window.setTimeout(() => {
      window.location.assign(autoRefresh.dataset.autoRefreshUrl);
    }, Math.max(delay, 3000));
  }
});
