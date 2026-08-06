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

  const resetSubmitLock = (form) => {
    form.dataset.submitting = "false";
    form.removeAttribute("aria-busy");
    form.querySelectorAll("[data-submit-disabled-by-lock]").forEach((control) => {
      control.disabled = false;
      control.removeAttribute("data-submit-disabled-by-lock");
      control.classList.remove("is-loading");
      control.removeAttribute("aria-busy");
      if (control.matches("input") && control.dataset.originalValue !== undefined) {
        control.value = control.dataset.originalValue;
        delete control.dataset.originalValue;
      } else if (control.dataset.originalContent !== undefined) {
        control.innerHTML = control.dataset.originalContent;
        delete control.dataset.originalContent;
      }
    });
    form.querySelectorAll("[data-submit-value-mirror]").forEach((input) => input.remove());
  };

  const lockSubmittedForm = (form, submitter) => {
    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");

    if (submitter?.name) {
      const mirror = document.createElement("input");
      mirror.type = "hidden";
      mirror.name = submitter.name;
      mirror.value = submitter.value;
      mirror.dataset.submitValueMirror = "true";
      form.appendChild(mirror);
    }

    const activeButton = submitter || form.querySelector('button[type="submit"], input[type="submit"]');
    if (activeButton) {
      const loadingLabel = activeButton.dataset.loadingLabel || "Traitement en cours…";
      activeButton.classList.add("is-loading");
      activeButton.setAttribute("aria-busy", "true");
      if (activeButton.matches("input")) {
        activeButton.dataset.originalValue = activeButton.value;
        activeButton.value = loadingLabel;
      } else {
        activeButton.dataset.originalContent = activeButton.innerHTML;
        const spinner = document.createElement("span");
        spinner.className = "ui-button__spinner";
        spinner.setAttribute("aria-hidden", "true");
        const label = document.createElement("span");
        label.textContent = loadingLabel;
        activeButton.replaceChildren(spinner, label);
      }
    }

    form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((control) => {
      if (!control.disabled) {
        control.disabled = true;
        control.dataset.submitDisabledByLock = "true";
      }
    });
  };

  document.querySelectorAll("form[data-confirm-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      if (form.dataset.confirmed === "true") return;
      event.preventDefault();
      if (form.dataset.confirmPending === "true") return;
      form.dataset.confirmPending = "true";
      const submitter = event.submitter;
      const title = form.dataset.confirmTitle || "Confirmer cette action ?";
      const text = form.dataset.confirmText || "";
      if (!window.Swal) {
        if (window.confirm(title)) {
          form.dataset.confirmed = "true";
          form.requestSubmit(submitter);
        }
        form.dataset.confirmPending = "false";
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
      form.dataset.confirmPending = "false";
      if (result.isConfirmed) {
        form.dataset.confirmed = "true";
        form.requestSubmit(submitter);
      }
    });
  });

  document.querySelectorAll('form[method="post"], form[data-submit-lock]').forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (event.defaultPrevented) return;
      if (form.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      lockSubmittedForm(form, event.submitter);
    });
  });

  window.addEventListener("pageshow", () => {
    document.querySelectorAll('form[data-submitting="true"]').forEach(resetSubmitLock);
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
