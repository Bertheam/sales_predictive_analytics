document.addEventListener("DOMContentLoaded", () => {
  const flashMessages = document.querySelectorAll("#flash-messages [data-message]");
  const levelIcons = { success: "success", error: "error", warning: "warning", info: "info" };

  const initializeIcons = () => {
    if (!window.lucide) return;
    window.lucide.createIcons({
      attrs: {
        "stroke-width": 1.8,
        "aria-hidden": "true",
      },
    });
  };

  initializeIcons();

  const initializeSelect = (element) => {
    if (!window.jQuery?.fn?.select2 || !element?.matches("select:not([data-native-select])")) return;
    const select = window.jQuery(element);
    if (element.closest(".swal2-container") || select.hasClass("swal2-select")) return;
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
  };

  const initializeSelects = (root) => {
    if (root.matches?.("select:not([data-native-select])")) initializeSelect(root);
    root.querySelectorAll?.("select:not([data-native-select])").forEach(initializeSelect);
  };

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

  initializeSelects(document);

  const productFreshness = document.querySelector("[data-product-freshness]");
  const productFreshnessData = document.querySelector("#product-freshness-data");
  const forecastProduct = document.querySelector('[name="product_id"]');
  if (productFreshness && productFreshnessData && forecastProduct) {
    let freshnessByProduct = {};
    try {
      freshnessByProduct = JSON.parse(productFreshnessData.textContent || "{}");
    } catch (_error) {
      freshnessByProduct = {};
    }
    const refreshProductFreshness = () => {
      const freshness = freshnessByProduct[forecastProduct.value] || {
        state: "missing",
        title: "Choisissez un produit",
        description: "Sa dernière vente sera vérifiée avant le calcul.",
        action_label: "Voir les ventes",
      };
      productFreshness.dataset.state = freshness.state;
      productFreshness.classList.toggle("is-stale", freshness.state !== "current");
      productFreshness.querySelector("[data-freshness-title]").textContent = freshness.title;
      productFreshness.querySelector("[data-freshness-description]").textContent = freshness.description;
      const action = productFreshness.querySelector("[data-freshness-action]");
      action.textContent = freshness.action_label || "Voir les ventes";
      action.hidden = freshness.state === "current";
      const submit = document.querySelector("[data-forecast-submit]");
      if (submit) {
        submit.disabled = freshness.state !== "current";
      }
    };
    forecastProduct.addEventListener("change", refreshProductFreshness);
    if (window.jQuery?.fn?.select2) {
      window.jQuery(forecastProduct).on("select2:select", refreshProductFreshness);
    }
    refreshProductFreshness();
  }

  document.querySelectorAll("[data-invitation-form]").forEach((form) => {
    const channel = form.querySelector('[name="channel"]');
    const panels = form.querySelectorAll("[data-contact-panel]");
    const refresh = () => {
      const selected = (channel?.value || (form.querySelector('[name="email"]')?.value ? "EMAIL" : "PHONE")).toUpperCase();
      panels.forEach((panel) => {
        const active = panel.dataset.contactPanel === selected;
        panel.hidden = !active;
        panel.classList.toggle("is-active", active);
        panel.querySelectorAll("input, select, textarea").forEach((field) => {
          field.disabled = !active;
        });
      });
    };
    channel?.addEventListener("change", refresh);
    channel?.addEventListener("input", refresh);
    if (channel && window.jQuery?.fn?.select2) {
      window.jQuery(channel).on("select2:select select2:clear", refresh);
    }
    refresh();
  });

  document.querySelectorAll("[data-copy-value]").forEach((button) => {
    button.addEventListener("click", async () => {
      const value = button.dataset.copyValue || "";
      try {
        await navigator.clipboard.writeText(value);
      } catch (_error) {
        const input = button.parentElement?.querySelector("input");
        input?.select();
        document.execCommand("copy");
      }
      if (window.Swal) {
        window.Swal.fire({
          toast: true,
          position: "top-end",
          icon: "success",
          title: "Lien copié",
          showConfirmButton: false,
          timer: 2200,
        });
      }
    });
  });

  document.querySelectorAll("[data-dynamic-formset]").forEach((formset) => {
    const prefix = formset.dataset.formPrefix;
    const totalInput = formset.querySelector(`#id_${prefix}-TOTAL_FORMS`);
    const maxInput = formset.querySelector(`#id_${prefix}-MAX_NUM_FORMS`);
    const rows = formset.querySelector("[data-form-rows]");
    const template = formset.querySelector("[data-empty-form-template]");
    const addButton = formset.querySelector("[data-add-form-row]");
    if (!totalInput || !rows || !template || !addButton) return;

    const activeRows = () => Array.from(rows.querySelectorAll("[data-form-row]")).filter((row) => {
      const deletionInput = row.querySelector(`[name$="-DELETE"]`);
      return !row.hidden && deletionInput?.value !== "on";
    });

    const refreshRows = () => {
      const currentRows = activeRows();
      currentRows.forEach((row, index) => {
        const number = row.querySelector(".line-number");
        if (number) number.textContent = String(index + 1).padStart(2, "0");
        const removeButton = row.querySelector("[data-remove-form-row]");
        if (removeButton) {
          removeButton.disabled = currentRows.length <= 1;
          removeButton.hidden = currentRows.length <= 1;
        }
      });
      const maximum = Number(maxInput?.value || 20);
      const reached = currentRows.length >= maximum;
      addButton.disabled = reached;
      addButton.hidden = reached;
    };

    rows.addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-remove-form-row]");
      if (!removeButton || activeRows().length <= 1) return;
      const row = removeButton.closest("[data-form-row]");
      const deletionInput = row?.querySelector(`[name$="-DELETE"]`);
      if (!row || !deletionInput) return;
      deletionInput.value = "on";
      row.querySelectorAll("input, select, textarea").forEach((field) => {
        if (field !== deletionInput) field.disabled = true;
      });
      row.hidden = true;
      refreshRows();
    });

    addButton.addEventListener("click", () => {
      const index = Number(totalInput.value);
      const maximum = Number(maxInput?.value || 20);
      if (index >= maximum) return;
      const number = String(index + 1).padStart(2, "0");
      const html = template.innerHTML
        .replaceAll("__prefix__", String(index))
        .replaceAll("__number__", number);
      rows.insertAdjacentHTML("beforeend", html);
      totalInput.value = String(index + 1);
      const newRow = rows.lastElementChild;
      initializeSelects(newRow);
      initializeIcons();
      newRow?.querySelector("select, input")?.focus();
      refreshRows();
    });
    refreshRows();
  });

  document.querySelectorAll("[data-import-wizard]").forEach((dialog) => {
    const stepPanels = Array.from(dialog.querySelectorAll("[data-import-step]"));
    const stepLinks = Array.from(dialog.querySelectorAll("[data-import-step-link]"));
    const progressLines = Array.from(dialog.querySelectorAll(".import-stepper > i"));
    const typeInputs = Array.from(dialog.querySelectorAll("[data-import-type]"));
    const selectedLabel = dialog.querySelector("[data-import-selected-label]");
    const uploadForm = dialog.querySelector("[data-import-upload-form]");
    const fileInput = uploadForm?.querySelector('input[type="file"]');
    const fileName = dialog.querySelector("[data-import-file-name]");
    const dropzone = dialog.querySelector(".import-dropzone");
    let currentStep = Number(dialog.dataset.startStep || 1);

    const selectedType = () => typeInputs.find((input) => input.checked);
    const refreshChoice = () => {
      const selected = selectedType();
      dialog.querySelectorAll("[data-import-choice]").forEach((card) => {
        card.classList.toggle("is-selected", card.contains(selected));
      });
      if (selectedLabel) selectedLabel.textContent = selected?.dataset.importLabel || "—";
    };

    const showStep = (step) => {
      const target = stepPanels.find((panel) => Number(panel.dataset.importStep) === step);
      if (!target || target.getAttribute("aria-hidden") === "true") return;
      currentStep = step;
      stepPanels.forEach((panel) => {
        panel.hidden = panel !== target;
      });
      stepLinks.forEach((link) => {
        const linkStep = Number(link.dataset.importStepLink);
        link.classList.toggle("is-active", linkStep === step);
        link.classList.toggle("is-complete", linkStep < step);
        link.setAttribute("aria-current", linkStep === step ? "step" : "false");
      });
      progressLines.forEach((line, index) => line.classList.toggle("is-complete", index + 1 < step));
      dialog.querySelector(".import-wizard__body")?.scrollTo({ top: 0, behavior: "smooth" });
      window.setTimeout(() => target.querySelector("input:checked, input:not([type=hidden]), button")?.focus(), 80);
    };

    const openDialog = (step = currentStep) => {
      showStep(step);
      if (!dialog.open) dialog.showModal();
      document.body.classList.add("has-open-dialog");
    };
    const closeDialog = () => {
      if (dialog.getAttribute("aria-busy") === "true") return;
      dialog.close();
    };

    document.querySelectorAll("[data-import-open]").forEach((button) => {
      button.addEventListener("click", () => openDialog(1));
    });
    dialog.querySelectorAll("[data-import-close]").forEach((button) => button.addEventListener("click", closeDialog));
    dialog.querySelectorAll("[data-import-next]").forEach((button) => {
      button.addEventListener("click", () => {
        if (!selectedType()) {
          window.Swal?.fire({ icon: "info", title: "Choisissez les données à importer", confirmButtonText: "D’accord" });
          return;
        }
        showStep(Number(button.dataset.importNext));
      });
    });
    dialog.querySelectorAll("[data-import-back]").forEach((button) => button.addEventListener("click", () => showStep(Number(button.dataset.importBack))));
    stepLinks.forEach((link) => {
      link.addEventListener("click", () => {
        const targetStep = Number(link.dataset.importStepLink);
        if (targetStep < currentStep) showStep(targetStep);
      });
    });
    typeInputs.forEach((input) => input.addEventListener("change", refreshChoice));

    const refreshFileName = () => {
      if (fileName) fileName.textContent = fileInput?.files?.[0]?.name || "Aucun fichier sélectionné";
      dropzone?.classList.toggle("has-file", Boolean(fileInput?.files?.length));
    };
    fileInput?.addEventListener("change", refreshFileName);
    ["dragenter", "dragover"].forEach((eventName) => dropzone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragging");
    }));
    ["dragleave", "drop"].forEach((eventName) => dropzone?.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragging");
    }));
    dropzone?.addEventListener("drop", (event) => {
      if (!fileInput || !event.dataTransfer?.files?.length) return;
      const transfer = new DataTransfer();
      transfer.items.add(event.dataTransfer.files[0]);
      fileInput.files = transfer.files;
      refreshFileName();
    });

    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog();
    });
    dialog.addEventListener("cancel", (event) => {
      if (dialog.getAttribute("aria-busy") === "true") event.preventDefault();
    });
    dialog.addEventListener("close", () => document.body.classList.remove("has-open-dialog"));
    uploadForm?.addEventListener("submit", (event) => {
      if (!fileInput?.files?.length) {
        event.preventDefault();
        dropzone?.classList.add("is-invalid");
        window.Swal?.fire({ icon: "info", title: "Choisissez votre fichier Excel", text: "Le fichier doit être au format XLSX.", confirmButtonText: "D’accord" });
      } else {
        dropzone?.classList.remove("is-invalid");
        dialog.setAttribute("aria-busy", "true");
      }
    });

    refreshChoice();
    refreshFileName();
    showStep(currentStep);
    if (dialog.dataset.autoOpen === "true") openDialog(currentStep);
  });

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
    form.closest("[data-import-wizard]")?.removeAttribute("aria-busy");
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
      form.closest("[data-import-wizard]")?.setAttribute("aria-busy", "true");
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
