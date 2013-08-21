#include "SkPdfType6ShadingDictionary_autogen.h"


#include "SkPdfNativeDoc.h"
int64_t SkPdfType6ShadingDictionary::BitsPerCoordinate(SkPdfNativeDoc* doc) {
  SkPdfNativeObject* ret = get("BitsPerCoordinate", "");
  if (doc) {ret = doc->resolveReference(ret);}
  if ((ret != NULL && ret->isInteger()) || (doc == NULL && ret != NULL && ret->isReference())) return ret->intValue();
  // TODO(edisonn): warn about missing required field, assert for known good pdfs
  return 0;
}

bool SkPdfType6ShadingDictionary::has_BitsPerCoordinate() const {
  return get("BitsPerCoordinate", "") != NULL;
}

int64_t SkPdfType6ShadingDictionary::BitsPerComponent(SkPdfNativeDoc* doc) {
  SkPdfNativeObject* ret = get("BitsPerComponent", "");
  if (doc) {ret = doc->resolveReference(ret);}
  if ((ret != NULL && ret->isInteger()) || (doc == NULL && ret != NULL && ret->isReference())) return ret->intValue();
  // TODO(edisonn): warn about missing required field, assert for known good pdfs
  return 0;
}

bool SkPdfType6ShadingDictionary::has_BitsPerComponent() const {
  return get("BitsPerComponent", "") != NULL;
}

int64_t SkPdfType6ShadingDictionary::BitsPerFlag(SkPdfNativeDoc* doc) {
  SkPdfNativeObject* ret = get("BitsPerFlag", "");
  if (doc) {ret = doc->resolveReference(ret);}
  if ((ret != NULL && ret->isInteger()) || (doc == NULL && ret != NULL && ret->isReference())) return ret->intValue();
  // TODO(edisonn): warn about missing required field, assert for known good pdfs
  return 0;
}

bool SkPdfType6ShadingDictionary::has_BitsPerFlag() const {
  return get("BitsPerFlag", "") != NULL;
}

SkPdfArray* SkPdfType6ShadingDictionary::Decode(SkPdfNativeDoc* doc) {
  SkPdfNativeObject* ret = get("Decode", "");
  if (doc) {ret = doc->resolveReference(ret);}
  if ((ret != NULL && ret->isArray()) || (doc == NULL && ret != NULL && ret->isReference())) return (SkPdfArray*)ret;
  // TODO(edisonn): warn about missing required field, assert for known good pdfs
  return NULL;
}

bool SkPdfType6ShadingDictionary::has_Decode() const {
  return get("Decode", "") != NULL;
}

SkPdfFunction SkPdfType6ShadingDictionary::Function(SkPdfNativeDoc* doc) {
  SkPdfNativeObject* ret = get("Function", "");
  if (doc) {ret = doc->resolveReference(ret);}
  if ((ret != NULL && ret->isFunction()) || (doc == NULL && ret != NULL && ret->isReference())) return ret->functionValue();
  // TODO(edisonn): warn about missing default value for optional fields
  return SkPdfFunction();
}

bool SkPdfType6ShadingDictionary::has_Function() const {
  return get("Function", "") != NULL;
}
